#	vim:fileencoding=utf-8
# (c) 2010 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

import os, re
from portage import VERSION as portage_ver

# live git tree generates 'vX.Y_rcZ-N-...'
# ebuilds use 'X.Y_rcZ_pN'
vmatch = re.match(r'^v?((?:\d+\.)*\d+)(?:_rc(\d+))?(?:(?:_p|-)(\d+))?', str(portage_ver))
if vmatch:
	vmatch = vmatch.groups()
	pv = [int(x) for x in vmatch[0].split('.')]

	if pv[0] >= 2 or (pv[0] == 2 and len(pv) >= 2 or pv[1] >= 2):
		if not vmatch[1] or int(vmatch[1]) > 72 or (int(vmatch[1]) == 72 and vmatch[2] and int(vmatch[2]) >= 12):
			sets_api = 1
		else:
			sets_api = 0
	else:
		raise ImportError('Portage version %s is not supported.' % portage_ver)
else:
	raise ImportError('Unable to parse the portage version: %s.' % portage_ver)

if sets_api == 0:
	from portage.sets.base import PackageSet
elif sets_api == 1:
	from portage._sets.base import PackageSet

from smartliverebuild.config import Config
from smartliverebuild.core import SmartLiveRebuild, SLRFailure

class SmartLiveRebuildSet(PackageSet):
	_operations = ["merge"]
	description = "Package set containing live packages awaiting update"

	def __init__(self, opts, vardbapi, portdbapi, settings):
		self._options = opts
		self._dbapi = vardbapi
		self._portdb = portdbapi
		self._settings = settings
		PackageSet.__init__(self)

	def load(self):
		# We're caching the resulting package in an environment
		# variable, using the pid as a safety measure to avoid random
		# data catching. This allows us to avoid updating all
		# the packages once again after emerge reloads itself.

		cachevar = 'PORTAGE_SLR_PACKAGE_LIST'
		pid = str(os.getpid())

		packages = os.environ.get(cachevar, '').split()
		if not packages or packages.pop(0) != pid:
			packages = None

		try:
			if packages is None:
				packages = SmartLiveRebuild(self._options,
						db = self._dbapi, portdb = self._portdb,
						settings = self._settings)
		except SLRFailure:
			pass
		else:
			self._setAtoms(packages)
			os.environ[cachevar] = ' '.join([pid] + packages)

	@classmethod
	def singleBuilder(cls, options, settings, trees):
		# Clasically, apply twice. First time to get configfile path
		# and profile; second time to override them.
		c = Config(settings)
		c.apply_dict(options)
		c.parse_configfiles()
		c.apply_dict(options)

		vardb = trees['vartree'].dbapi
		portdb = trees['porttree'].dbapi

		return cls(c.get_options(), vardb, portdb, settings)
