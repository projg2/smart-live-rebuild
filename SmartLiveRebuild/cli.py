from optparse import OptionParser

from SmartLiveRebuild import PV

def parse_options(argv):
	opt = OptionParser(
			usage='%prog [options] -- [emerge options]',
			version='%%prog %s' % PV,
			description='Enumerate all live packages in system, check their repositories for updates and remerge the updated ones.'
	)
	opt.add_option('-c', '--config-file', action='store', dest='config_file',
		help='Configuration file (default: /etc/portage/smart-live-rebuild.conf)')
	opt.add_option('-C', '--no-color', action='store_false', dest='color',
		help='Disable colorful output.')
	opt.add_option('-E', '--no-erraneous-merge', action='store_false', dest='erraneous_merge',
		help='Disable emerging packages for which the update has failed.')
	opt.add_option('-j', '--jobs', action='store', type='int', dest='jobs',
		help='Spawn JOBS parallel processes to perform repository updates.')
	opt.add_option('-l', '--local-rev', action='store_true', dest='local_rev',
		help='Force determining the current package revision from the repository instead of using the one saved by portage.')
	opt.add_option('-N', '--no-network', action='store_false', dest='network',
		help='Disable network interaction and just aggregate already updated repositories (requires --local-rev not set).')
	opt.add_option('-O', '--no-offline', action='store_false', dest='offline',
		help='Disable setting ESCM_OFFLINE for emerge.')
	opt.add_option('-p', '--pretend', action='store_true', dest='pretend',
		help='Only print a list of the packages which were updated; do not call emerge to rebuild them.')
	opt.add_option('-P', '--profile', action='store', dest='profile',
		help='Configuration profile (config file section) to use (default: smart-live-rebuild)')
	opt.add_option('-Q', '--quickpkg', action='store_true', dest='quickpkg',
		help='Call quickpkg to create binary backups of packages which are going to be updated.')
	opt.add_option('-S', '--no-setuid', action='store_false', dest='setuid',
		help='Do not switch UID to portage when FEATURES=userpriv is set.')
	opt.add_option('-t', '--type', action='append', dest='type',
		help='Limit rebuild to packages using specific VCS (eclass name). If used multiple times, all specified VCS-es will be used.')
	opt.add_option('-U', '--unprivileged-user', action='store_true', dest='unprivileged_user',
		help='Allow running as an unprivileged user.')

	return opt.parse_args(argv[1:])
