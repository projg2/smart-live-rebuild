# 	vim:fileencoding=utf-8:noet
# (c) 2010 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

import os, re

from gentoopm import get_package_manager

from portage._sets.base import PackageSet

from smartliverebuild.config import Config
from smartliverebuild.core import SmartLiveRebuild, SLRFailure


class SmartLiveRebuildSet(PackageSet):
    _operations = ["merge"]
    description = "Package set containing live packages awaiting update"

    def __init__(self, opts):
        self._options = opts
        PackageSet.__init__(self)

    def load(self):
        # Clasically, apply twice. First time to get configfile path
        # and profile; second time to override them.

        pm = get_package_manager()
        c = Config(pm.config)
        c.apply_dict(self._options)
        c.parse_configfiles()
        c.apply_dict(self._options)

        # We're caching the resulting package in an environment
        # variable, using the pid as a safety measure to avoid random
        # data catching. This allows us to avoid updating all
        # the packages once again after emerge reloads itself.

        cachevar = "PORTAGE_SLR_PACKAGE_LIST"
        pid = str(os.getpid())

        packages = os.environ.get(cachevar, "").split()
        if not packages or packages.pop(0) != pid:
            packages = None

        try:
            if packages is None:
                packages = SmartLiveRebuild(c.get_options(), pm)
        except SLRFailure:
            pass
        else:
            self._setAtoms(packages)
            os.environ[cachevar] = " ".join([pid] + packages)

    @classmethod
    def singleBuilder(cls, options, settings, trees):
        return cls(options)
