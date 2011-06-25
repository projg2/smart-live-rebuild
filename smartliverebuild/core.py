#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

import bz2, errno, fcntl, os, os.path, pickle, select, shutil, signal, subprocess, sys, tempfile, time
import fnmatch, re # for PackageFilter

from portage import create_trees
from portage.data import portage_uid, portage_gid
from portage.versions import catpkgsplit, pkgsplit

from smartliverebuild.output import out
from smartliverebuild.vcs import NonLiveEbuild

class SLRFailure(Exception):
	pass

class BashParser(object):
	def __init__(self):
		self._tmpf = tempfile.NamedTemporaryFile('w+b')
		self._bashproc = subprocess.Popen(['bash', '-c',
				'while read -r SLR_VARS; do ( source %s; eval set -- ${SLR_VARS}; printf "%%s\\0" "${@}" ); done' % self._tmpf.name],
			stdin = subprocess.PIPE, stdout = subprocess.PIPE)

		fd = self._bashproc.stdout
		fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK | fcntl.fcntl(fd, fcntl.F_GETFL))

	def grabenv(self, envf):
		f = self._tmpf
		f.seek(0, 0)
		f.truncate(0)
		shutil.copyfileobj(envf, f)
		f.flush()

	def __call__(self, vars):
		# File ready, now ping the server...
		self._bashproc.stdin.write(('%s\n' % ' '.join(['"${%s}"' % x for x in vars])).encode('ASCII'))
		self._bashproc.stdin.flush()

		# ...and grab the output (hopefully, we're in non-blocking mode).
		l = bytes()
		spl = []
		while len(spl) <= len(vars):
			select.select((self._bashproc.stdout,), (), (), 5)
			try:
				ret = self._bashproc.stdout.read()
				if ret is None:
					continue
				l += ret
			except IOError as e:
				if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
					raise
			else:
				try:
					# the environment file should be utf8-encoded
					spl = l.decode('utf8').split('\0')
				except UnicodeError:
					# got stuck in the middle of a character?
					spl = []

		return dict(zip(vars, spl))

	def terminate(self):
		self._bashproc.terminate()
		self._bashproc.communicate()
		self._tmpf.close()

wildcard_re = re.compile(r'^(!)?(?:([A-Za-z0-9+_.?*\[\]-]+)/)?([A-Za-z0-9+_?*\[\]-]+)$')
class PackageFilter(object):
	""" Package filtering framework. """

	class PackageMatcher(object):
		""" A single package filter. """

		def __init__(self, wildcard):
			""" Init filter for pattern. """
			m = wildcard_re.match(wildcard)
			self.broken = not m

			def makere(s):
				return re.compile(r'^%s$' % fnmatch.translate(s))

			if not self.broken:
				self.exclusive = bool(m.group(1))
				if m.group(2):
					self.category = makere(m.group(2))
				else:
					self.category = re.compile('.')
				self.pn = makere(m.group(3))
#			XXX: the below test catches cliargs as well
#			else:
#				sys.stderr.write('Incorrect filter string: %s\n' % wildcard)

			# .matched is used only on inclusive args
			self.matched = self.exclusive
			self.wildcard = wildcard

		def __call__(self, cpv):
			cat, pkg, ver, rev = catpkgsplit(cpv)
			m = bool(self.category.match(cat) and self.pn.match(pkg))
			self.matched |= m
			return m ^ self.exclusive

	def __init__(self, wlist):
		""" Init filters from pattern list. """
		if wlist:
			pmatchers = [self.PackageMatcher(w) for w in wlist]
			self._broken = filter(lambda f: f.broken, pmatchers)
			self._pmatchers = filter(lambda f: not f.broken, pmatchers)
			for f in self._pmatchers:
				self._default_pass = f.exclusive
				break
		else:
			self._pmatchers = ()
			self._default_pass = True

	def __call__(self, cpv):
		""" Execute filtering on CPV. """
		r = self._default_pass
		for m in self._pmatchers:
			if m.exclusive:
				r &= m(cpv)
			else:
				r |= m(cpv)
		return r

	@property
	def nonmatched(self):
		""" Iterate over non-matched args. """

		for m in self._pmatchers:
			if not m.matched:
				yield m.wildcard
		for m in self._broken:
			yield m.wildcard

class VCSLoader(object):
	vcs_cache = {}

	def __call__(self, eclassname, allowed = []):
		if eclassname not in self.vcs_cache:
			if allowed and eclassname not in allowed:
				self.vcs_cache[eclassname] = None
			else:
				modname = 'smartliverebuild.vcs.%s' % eclassname.replace('-', '_')
				try:
					mod = __import__(modname, {}, {}, ['.'], 0)
				except ImportError:
					self.vcs_cache[eclassname] = None
				else:
					for k in dir(mod):
						if k.endswith('Support') and \
								k[:-7].lower() == eclassname.replace('-', ''):
							self.vcs_cache[eclassname] = getattr(mod, k)
							break
					else:
						raise ImportError('Unable to find a matching class in %s' % modname)

		return self.vcs_cache[eclassname]

GetVCS = VCSLoader()

def SmartLiveRebuild(opts, db = None, portdb = None, settings = None,
		cliargs = None):
	if db is None or portdb is None or settings is None:
		trees = create_trees(
				config_root = os.environ.get('PORTAGE_CONFIGROOT'),
				target_root = os.environ.get('ROOT'))
		tree = trees[max(trees)]
		if db is None:
			db = tree['vartree'].dbapi
		if portdb is None:
			portdb = tree['porttree'].dbapi
		if settings is None:
			settings = db.settings

	if not opts.color:
		out.monochromize()

	if opts.jobs <= 0:
		out.err('The argument to --jobs option must be a positive integer.')
		raise SLRFailure('')

	childpid = None
	commpipe = None
	userok = (os.geteuid() == 0)
	if opts.setuid:
		if portage_uid and portage_gid:
			if not userok:
				if os.getuid() == portage_uid:
					userok = True
			else:
				out.s1('Forking to drop superuser privileges ...')
				commpipe = os.pipe()
				childpid = os.fork()
		else:
			out.err("setuid requested but there's no 'portage' user in the system")
			return 1

	if not opts.unprivileged_user and not userok:
		out.err('Either superuser or portage privileges are required!')
		out.out('''
This tool requires either superuser or portage (if FEATURES=userpriv is set)
privileges. If you would like to force running the update using your current
user account, please pass the --unprivileged-user option.
''')
		raise SLRFailure('')

	try:
		if not childpid:
			if childpid == 0:
				os.close(commpipe[0])
				# Make sure CWD will be readable to portage user
				os.chdir('/')
				os.setuid(portage_uid)
			if opts.type:
				allowed = frozenset(opts.type)
			else:
				allowed = None

			if opts.jobs == 1:
				out.s1('Updating the repositories...')
			else:
				out.s1('Updating the repositories using %s%d%s parallel jobs...' % (out.white, opts.jobs, out.s1reset))

			atoms = db.cpv_all()
			processes = []

			packages = []
			erraneous = []
			rebuilds = {}

			def loop_iter(blocking = False):
				needsleep = True
				for i, vcs in reversed(list(enumerate(processes[:opts.jobs]))):
					try:
						ret = vcs(blocking)
						if ret is not None:
							needsleep = False
							if ret:
								packages.extend(vcs.cpv)
							del processes[i]
					except KeyboardInterrupt:
						raise
					except Exception as e:
						out.err('Error updating %s: [%s] %s' % (vcs.cpv, e.__class__.__name__, e))
						erraneous.extend(vcs.cpv)
						del processes[i]
				return needsleep

			bash = BashParser()

			filters = (opts.filter_packages or []) + (cliargs or [])
			filt = PackageFilter(filters)

			try:
				try:
					while atoms:
						cpv = atoms.pop(0)
						if not filt(cpv):
							continue

						try:
							aux = db.aux_get(cpv, ['INHERITED', 'SLOT'])
							inherits = aux[0].split()
							slot = aux[1]
							if slot:
								slottedcpv = '%s:%s' % (cpv, slot)
							else:
								slottedcpv = cpv

							for vcs in inherits:
								vcscl = GetVCS(vcs, allowed)
								if vcscl is not None:
									env = bz2.BZ2File('%s/environment.bz2' % db.getpath(cpv), 'r')
									bash.grabenv(env)
									vcs = vcscl(slottedcpv, bash, opts, settings)
									env.close()

									uri = str(vcs)
									if uri not in rebuilds:
										rebuilds[uri] = vcs
										processes.append(vcs)
										loop_iter()
									elif rebuilds[uri] in processes:
										rebuilds[uri] += vcs
									elif rebuilds[uri].cpv[0] in packages:
										packages.extend(vcs.cpv)
									elif rebuilds[uri].cpv[0] in erraneous:
										erraneous.extend(vcs.cpv)
						except KeyboardInterrupt:
							raise
						except NonLiveEbuild as e:
							out.err('%s: %s' % (cpv, e))
						except Exception as e:
							out.err('Error enumerating %s: [%s] %s' % (cpv, e.__class__.__name__, e))
							erraneous.append(cpv)
				finally:
					bash.terminate()

				while processes:
					if loop_iter((opts.jobs == 1)):
						time.sleep(0.3)
			except KeyboardInterrupt:
				out.err('Updates interrupted, proceeding with already updated repos.')
				for vcs in processes:
					vcs.abortupdate()

			if cliargs:
				nm = set(filt.nonmatched)
				for i, el in enumerate(cliargs):
					if el not in nm:
						del cliargs[i]

			if childpid == 0:
				pdata = {'packages': packages, 'erraneous': erraneous}
				pipe = os.fdopen(commpipe[1], 'wb')
				pickle.dump(pdata, pipe, pickle.HIGHEST_PROTOCOL)
				pipe.flush()
				pipe.close()
				os._exit(0)
		else:
			os.close(commpipe[1])
			pipe = os.fdopen(commpipe[0], 'rb')
			sigint = signal.getsignal(signal.SIGINT)
			signal.signal(signal.SIGINT, signal.SIG_IGN)
			try:
				pdata = pickle.load(pipe)
			except EOFError: # child terminated early
				raise SLRFailure('')
			signal.signal(signal.SIGINT, sigint)
			packages = pdata['packages']
			erraneous = pdata['erraneous']

		if opts.erraneous_merge and len(erraneous) > 0:
			packages.extend(erraneous)

		if opts.quickpkg and len(packages) >= 1:
			out.s1('Calling quickpkg to create %s%d%s binary packages ...' % (out.white, len(packages), out.s1reset))

			# backwards compat, nowadays quickpkg is in ${PATH}
			if os.path.exists('/usr/sbin/quickpkg'):
				cmd = ['/usr/sbin/quickpkg']
			else:
				cmd = ['quickpkg']
			cmd.append('--include-config=y')
			cmd.extend(['=%s' % x for x in packages])
			out.s2(' '.join(cmd))
			subprocess.Popen(cmd, stdout=sys.stderr).wait()

		def mypkgcut(slottedcpv, n):
			""" Return n first components of split-joined slottedcpv. """
			splitcpv = slottedcpv.rsplit(':', 1)
			splitcpv[0] = '-'.join(pkgsplit(splitcpv[0])[0:n])
			return ':'.join(splitcpv)

		if opts.allow_downgrade == 'always':
			packages = [mypkgcut(x, 1) for x in packages]
		else:
			if opts.allow_downgrade == 'same-pv':
				packages = [mypkgcut(x, 2) for x in packages]
			packages = ['>=%s' % x for x in packages]

		# Check portdb for matches. Drop unmatched packages.
		for p in list(packages):
			if not portdb.match(p):
				out.err('No packages matching %s in portdb, skipping.' % p)
				packages.remove(p)

		if len(packages) < 1:
			out.s1('No updates found')
		else:
			out.s1('Found %s%d%s packages to rebuild.' % (out.white, len(packages), out.s1reset))
	finally:
		if childpid: # make sure that we leave no orphans
			os.kill(childpid, signal.SIGTERM)

	return packages