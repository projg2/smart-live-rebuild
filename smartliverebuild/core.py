#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

import bz2, os, os.path, pickle, signal, subprocess, sys, time

from portage import create_trees
from portage.data import portage_uid, portage_gid
from portage.versions import pkgsplit

from smartliverebuild.bashparse import BashParser
from smartliverebuild.filtering import PackageFilter
from smartliverebuild.output import out
from smartliverebuild.vcs import NonLiveEbuild
from smartliverebuild.vcsload import VCSLoader

class SLRFailure(Exception):
	pass

def SmartLiveRebuild(opts, pm, cliargs = None):
	if not opts.color:
		out.monochromize()

	if opts.jobs <= 0:
		out.err('The argument to --jobs option must be a positive integer.')
		raise SLRFailure('')

	childpid = None
	commpipe = None
	userok = (os.geteuid() == 0)
	if opts.setuid:
		pm_conf = pm.config
		portage_uid = pm_conf.userpriv_uid
		portage_gid = pm_conf.userpriv_gid
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

			filters = (opts.filter_packages or []) + (cliargs or [])
			filt = PackageFilter(filters)
			getvcs = VCSLoader()

			try:
				for pkg in pm.installed:
					if not filt(pkg.key):
						continue

					try:
						inherits = pkg.metadata['INHERITED'].split()

						for vcs in inherits:
							vcscl = getvcs(vcs, allowed, remote_only = opts.remote_only)
							if vcscl is not None:
								vcs = vcscl(str(pkg.atom.slotted), pkg.environ, opts)

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
						out.err('%s: %s' % (pkg.id, e))
					except Exception as e:
						if opts.debug:
							raise
						out.err('Error enumerating %s: [%s] %s' % (pkg.id, e.__class__.__name__, e))
						erraneous.append(str(pkg.atom.slotted))

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

			packages = [str(p) for p in packages]
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

		if len(packages) < 1:
			out.s1('No updates found')
		else:
			out.s1('Found %s%d%s packages to rebuild.' % (out.white, len(packages), out.s1reset))
	finally:
		if childpid: # make sure that we leave no orphans
			os.kill(childpid, signal.SIGTERM)

	return packages
