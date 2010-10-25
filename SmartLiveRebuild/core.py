#	vim:fileencoding=utf-8
# (c) 2010 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

import bz2, errno, fcntl, os.path, pickle, select, shutil, signal, subprocess, sys, tempfile, time
import portage
from portage.versions import pkgsplit

from SmartLiveRebuild.output import out
from SmartLiveRebuild.vcs import NonLiveEbuild, GetVCS

class SLRFailure(Exception):
	pass

class BashParser(object):
	def __init__(self):
		self._tmpf = tempfile.NamedTemporaryFile('w+b')
		self._bashproc = subprocess.Popen(['bash', '-c',
				'while read -r SLR_VARS; do source %s; eval set -- ${SLR_VARS}; printf "%%s\\0" "${@}"; done' % self._tmpf.name],
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

def SmartLiveRebuild(opts, db = None, portdb = None, saveuid = False, settings = None):
	if settings is None:
		settings = portage.settings
	if db is None or portdb is None:
		trees = portage.create_trees()
		if db is None:
			db = trees[settings['ROOT']]['vartree'].dbapi
		if portdb is None:
			portdb = trees[settings['ROOT']]['porttree'].dbapi

	if not opts.color:
		out.monochromize()

	if opts.local_rev and not opts.network:
		out.err('The --local-rev and --no-network options can not be specified together.')
		raise SLRFailure('')
	if opts.jobs <= 0:
		out.err('The argument to --jobs option must be a positive integer.')
		raise SLRFailure('')
	elif opts.jobs > 1 and not opts.network:
		out.s1('Using parallel jobs with --no-network is inefficient, assuming no --jobs.')
		opts.jobs = 1

	childpid = None
	commpipe = None
	userok = (os.geteuid() == 0)
	if opts.setuid:
		puid = portage.data.portage_uid
		pgid = portage.data.portage_gid
		if puid and pgid:
			if not userok:
				if os.getuid() == puid:
					userok = True
			elif not saveuid and not opts.quickpkg:
				out.s1('Dropping superuser privileges ...')
				os.setuid(puid)
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
				os.setuid(puid)
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
			try:
				try:
					while atoms:
						cpv = atoms.pop(0)

						try:
							inherits = db.aux_get(cpv, ['INHERITED'])[0].split()

							for vcs in inherits:
								vcscl = GetVCS(vcs, allowed)
								if vcscl is not None:
									env = bz2.BZ2File('%s/environment.bz2' % db.getpath(cpv), 'r')
									bash.grabenv(env)
									vcs = vcscl(cpv, bash, opts, settings)
									env.close()
									if opts.network or vcs.getsavedrev():
										dir = vcs.getpath()
										if dir not in rebuilds:
											rebuilds[dir] = vcs
											processes.append(vcs)
											loop_iter()
										elif rebuilds[dir] in processes:
											rebuilds[dir].append(vcs)
										elif rebuilds[dir].cpv[0] in packages:
											packages.extend(vcs.cpv)
										elif rebuilds[dir].cpv[0] in erraneous:
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

		if opts.offline:
			if opts.erraneous_merge and len(erraneous) > 0:
				out.s1('Merging update-failed packages, assuming --no-offline.')
				opts.offline = False
			else:
				os.environ['ESCM_OFFLINE'] = 'true'

		if opts.allow_downgrade == 'always':
			packages = [pkgsplit(x)[0] for x in packages]
		else:
			if opts.allow_downgrade == 'same-pv':
				packages = ['-'.join(pkgsplit(x)[0:2]) for x in packages]
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
