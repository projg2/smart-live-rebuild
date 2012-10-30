#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

import os, os.path, pickle, signal, subprocess, sys, time

from .filtering import PackageFilter
from .output import out
from .vcs import NonLiveEbuild
from .vcsload import VCSLoader

class SLRFailure(Exception):
	pass

def SmartLiveRebuild(opts, pm, cliargs = None):
	if not opts.color:
		out.monochromize()
	if opts.quiet:
		out.silence()

	if opts.jobs <= 0:
		out.err('The argument to --jobs option must be a positive integer.')
		raise SLRFailure('')

	childpid = None
	commpipe = None
	superuser = (os.geteuid() == 0)
	if opts.setuid:
		pm_conf = pm.config
		portage_uid = pm_conf.userpriv_uid
		portage_gid = pm_conf.userpriv_gid
		if portage_uid and portage_gid:
			if superuser:
				out.s1('Forking to drop superuser privileges ...')
				commpipe = os.pipe()
				childpid = os.fork()
		else:
			out.err("setuid requested but there's no 'portage' user in the system")
			return 1

	if not superuser and not opts.unprivileged_user:
		out.err('Superuser privileges are required!')
		out.out('''
This tool requires superuser privileges. If you would like to force running
the update using your current user account, please pass the --unprivileged-user
option.
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

			processes = []

			packages = []
			erraneous = []
			cache = {}

			def loop_iter(blocking = False):
				needsleep = True
				for i, vcs in reversed(list(enumerate(processes[:opts.jobs]))):
					try:
						ret = vcs(blocking)
						if ret is not None:
							needsleep = False
							if ret:
								packages.append(vcs.cpv)
							del processes[i]
					except KeyboardInterrupt:
						raise
					except Exception as e:
						if opts.debug:
							raise
						out.err('Error updating %s: [%s] %s' % (vcs.cpv, e.__class__.__name__, e))
						erraneous.append(vcs.cpv)
						del processes[i]
						cache[str(vcs)] = e
				return needsleep

			filters = (opts.filter_packages or []) + (cliargs or [])
			filt = PackageFilter(filters)
			getvcs = VCSLoader(remote_only = opts.remote_only)

			try:
				for pkg in pm.installed.filter(filt):
					try:
						for vcs in pkg.inherits:
							vcscl = getvcs(vcs, allowed)
							if vcscl is not None:
								vcs = vcscl(str(pkg.slotted_atom),
										environ = pkg.environ,
										opts = opts,
										cache = cache)
								processes.append(vcs)
								loop_iter()
					except KeyboardInterrupt:
						raise
					except NonLiveEbuild as e:
						out.s2('[%s]' % pkg.slotted_atom)
						out.s3('%s%s%s' % (out.brown, e, out.reset))
					except Exception as e:
						if opts.debug:
							raise
						out.err('Error enumerating %s: [%s] %s' % (pkg, e.__class__.__name__, e))
						erraneous.append(str(pkg.slotted_atom))

				while processes:
					if loop_iter((opts.jobs == 1)):
						time.sleep(0.3)
			except KeyboardInterrupt:
				out.err('Updates interrupted, proceeding with already updated repos.')
				for vcs in processes:
					del vcs

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

		# Check portdb for matches. Drop unmatched packages.
		for p in list(packages):
			if pm.Atom(p) not in pm.stack:
				out.err('No packages matching %s in portdb, skipping.' % p)
				packages.remove(p)

		if not opts.pretend and opts.quickpkg and len(packages) >= 1:
			out.s1('Calling quickpkg to create %s%d%s binary packages ...' % (out.white, len(packages), out.s1reset))

			# backwards compat, nowadays quickpkg is in ${PATH}
			if os.path.exists('/usr/sbin/quickpkg'):
				cmd = ['/usr/sbin/quickpkg']
			else:
				cmd = ['quickpkg']
			cmd.append('--include-config=y')
			cmd.extend(packages)
			out.s2(' '.join(cmd))
			subprocess.Popen(cmd, stdout=sys.stderr).wait()

		if len(packages) < 1:
			out.result('No updates found')
		else:
			out.result('Found %s%d%s packages to rebuild.' % (out.white, len(packages), out.s1reset))
	finally:
		if childpid: # make sure that we leave no orphans
			try:
				os.kill(childpid, signal.SIGTERM)
			except OSError:
				pass

	return packages
