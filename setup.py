#!/usr/bin/python
#	vim:fileencoding=utf-8
# (c) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

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

		packages = ['SmartLiveRebuild', 'SmartLiveRebuild.vcs'],
		scripts = ['smart-live-rebuild'],

		classifiers = [
			'Development Status :: 4 - Beta',
			'Environment :: Console',
			'Environment :: Plugins',
			'Intended Audience :: System Administrators',
			'License :: OSI Approved :: BSD License',
			'License :: OSI Approved :: GNU General Public License (GPL)',
			'Operating System :: POSIX',
			'Programming Language :: Python',
			'Topic :: System :: Installation/Setup'
		]
)
