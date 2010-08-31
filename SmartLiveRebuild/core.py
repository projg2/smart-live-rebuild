import bz2, os.path, pickle, signal, subprocess, sys, tempfile, time
import portage

from SmartLiveRebuild.output import out
from SmartLiveRebuild.vcs import NonLiveEbuild

def SmartLiveRebuild(opts, args, vcsl):
	if not opts.color:
		out.monochromize()

	if not opts.pretend:
		try:
			import psutil

			def getproc(pid):
				for ps in psutil.get_process_list():
					if pid == ps.pid:
						return ps
				raise Exception()

			def getscriptname(ps):
				if os.path.basename(ps.cmdline[0]) != ps.name:
					return ps.cmdline[0]
				cmdline = ps.cmdline[1:]
				while cmdline[0].startswith('-'): # omit options
					cmdline.pop(0)
				return os.path.basename(cmdline[0])

			ps = getproc(os.getppid())
			# traverse upstream to find the emerge process
			while ps.pid > 1:
				if getscriptname(ps) == 'emerge':
					out.s1('Running under the emerge process, assuming --pretend.')
					opts.pretend = True
					break
				ps = ps.parent
		except Exception:
			pass

	if opts.setuid and 'userpriv' not in portage.settings.features:
		out.err('setuid requested but FEATURES=userpriv not set, assuming --no-setuid.')
		opts.setuid = False
	if opts.local_rev and not opts.network:
		out.err('The --local-rev and --no-network options can not be specified together.')
		return 1
	if opts.jobs <= 0:
		out.err('The argument to --jobs option must be a positive integer.')
		return 1
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
					if not opts.pretend:
						out.s1('Running as the portage user, assuming --pretend.')
						opts.pretend = True
					if opts.quickpkg:
						out.err("Running as the portage user, --quickpkg probably won't work")
					userok = True
			elif opts.pretend and not opts.quickpkg:
				out.s1('Dropping superuser privileges ...')
				os.setuid(puid)
			else:
				out.s1('Forking to drop superuser privileges ...')
				commpipe = os.pipe()
				childpid = os.fork()
		else:
			out.err("'userpriv' is set but there's no 'portage' user in the system")

	if not opts.unprivileged_user and not userok:
		out.err('Either superuser or portage privileges are required!')
		out.out('''
This tool requires either superuser or portage (if FEATURES=userpriv is set)
privileges. If you would like to force running the update using your current
user account, please pass the --unprivileged-user option.
''')
		return 1

	try:
		if not childpid:
			if childpid == 0:
				os.close(commpipe[0])
				os.setuid(puid)
			if opts.type:
				vcslf = [x for x in vcsl if x.inherit in opts.type]
			else:
				vcslf = vcsl

			out.s1('Enumerating the packages ...')

			erraneous = []
			rebuilds = {}

			envtmpf = tempfile.NamedTemporaryFile('w+b')
			try:
				db = portage.db[portage.settings['ROOT']]['vartree'].dbapi
				for cpv in db.cpv_all():
					try:
						inherits = db.aux_get(cpv, ['INHERITED'])[0].split()

						for vcs in vcslf:
							if vcs.match(inherits):
								env = bz2.BZ2File('%s/environment.bz2' % db.getpath(cpv), 'r')
								vcs = vcs(cpv, env, envtmpf, opts)
								env.close()
								if opts.network or vcs.getsavedrev():
									dir = vcs.getpath()
									if dir not in rebuilds:
										rebuilds[dir] = vcs
									else:
										rebuilds[dir].append(vcs)
					except KeyboardInterrupt:
						raise
					except NonLiveEbuild as e:
						out.err('%s: %s' % (cpv, e))
					except Exception as e:
						out.err('Error enumerating %s: [%s] %s' % (cpv, e.__class__.__name__, e))
						erraneous.append(cpv)
			finally:
				envtmpf.close()

			if opts.jobs == 1:
				out.s1('Updating the repositories...')
			else:
				out.s1('Updating the repositories using %s%d%s parallel jobs...' % (out.white, opts.jobs, out.s1reset))
			packages = []

			processes = []
			items = list(rebuilds.items())
			while True:
				try:
					if len(processes) < opts.jobs and len(items) > 0:
						(dir, vcs) = items.pop(0)
						try:
							vcs.startupdate()
							if opts.jobs == 1:
								ret = vcs.endupdate(True)
							else:
								processes.append(vcs)
						except KeyboardInterrupt:
							vcs.abortupdate()
							raise
					elif len(processes) == 0: # which is true if jobs == 1 too
						break
					else:
						time.sleep(0.3)

					for vcs in processes:
						ret = vcs.endupdate()
						if ret is not None:
							processes.remove(vcs)
							break

					if ret:
						packages.extend(vcs.cpv)
				except KeyboardInterrupt:
					out.err('Updates interrupted, proceeding with already updated repos.')
					for vcs in processes:
						vcs.abortupdate()
					break
				except Exception as e:
					out.err('Error updating %s: [%s] %s' % (vcs.cpv, e.__class__.__name__, e))
					if opts.jobs != 1 and vcs in processes:
						processes.remove(vcs)
					erraneous.extend(vcs.cpv)

			if childpid == 0:
				pdata = {'packages': packages, 'erraneous': erraneous}
				pipe = os.fdopen(commpipe[1], 'wb')
				pickle.dump(pdata, pipe, pickle.HIGHEST_PROTOCOL)
				return 0
		else:
			os.close(commpipe[1])
			pipe = os.fdopen(commpipe[0], 'rb')
			sigint = signal.getsignal(signal.SIGINT)
			signal.signal(signal.SIGINT, signal.SIG_IGN)
			try:
				pdata = pickle.load(pipe)
			except EOFError: # child terminated early
				return 1
			signal.signal(signal.SIGINT, sigint)
			packages = pdata['packages']
			erraneous = pdata['erraneous']

		if opts.erraneous_merge and len(erraneous) > 0:
			packages.extend(erraneous)

		if opts.quickpkg and len(packages) >= 1:
			out.s1('Calling quickpkg to create %s%d%s binary packages ...' % (out.white, len(packages), out.s1reset))
			cmd = ['/usr/sbin/quickpkg', '--include-config=y']
			cmd.extend(['=%s' % x for x in packages])
			out.s2(' '.join(cmd))
			subprocess.Popen(cmd, stdout=sys.stderr).wait()

		if len(packages) < 1:
			out.s1('No updates found')
		elif opts.pretend:
			out.s1('Printing a list of updated packages ...')
			if opts.erraneous_merge and len(erraneous) > 0:
				out.s2('(please notice that it contains the update-failed ones as well)')
			for p in packages:
				print('>=%s' % p)
		else:
			if opts.erraneous_merge and len(erraneous) > 0:
				if opts.offline:
					out.s1('Merging update-failed packages, assuming --no-offline.')
					opts.offline = False

			out.s1('Calling emerge to rebuild %s%d%s packages ...' % (out.white, len(packages), out.s1reset))
			if opts.offline:
				os.putenv('ESCM_OFFLINE', 'true')
			cmd = ['emerge', '--oneshot']
			cmd.extend(args)
			cmd.extend(['>=%s' % x for x in packages])
			out.s2(' '.join(cmd))
			os.execv('/usr/bin/emerge', cmd)
	finally:
		if childpid: # make sure that we leave no orphans
			os.kill(childpid, signal.SIGTERM)

	return 0

