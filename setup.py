#!/usr/bin/python
#	vim:fileencoding=utf-8

from distutils.core import setup

import os.path, sys

sys.path.insert(0, os.path.dirname(sys.argv[0]))
try:
	from SmartLiveRebuild import PV
except ImportError:
	PV = 'unknown'

setup(
		name = 'smart-live-rebuild',
		version = PV,
		author = 'Michał Górny',
		author_email = 'gentoo@mgorny.alt.pl',
		url = 'http://github.com/mgorny/smart-live-rebuild',

		packages = ['SmartLiveRebuild'],
		scripts = ['smart-live-rebuild']
)
