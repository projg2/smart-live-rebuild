#!/usr/bin/python
#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

from distutils.core import setup

import os.path, sys

sys.path.insert(0, os.path.dirname(__file__))
try:
	from smartliverebuild import PV
except ImportError:
	PV = 'unknown'

setup(
		name = 'smart-live-rebuild',
		version = PV,
		author = 'Michał Górny',
		author_email = 'mgorny@gentoo.org',
		url = 'http://github.com/mgorny/smart-live-rebuild',

		packages = ['smartliverebuild', 'smartliverebuild.vcs'],
		scripts = ['smart-live-rebuild'],

		classifiers = [
			'Development Status :: 5 - Production/Stable',
			'Environment :: Console',
			'Environment :: Plugins',
			'Intended Audience :: System Administrators',
			'License :: OSI Approved :: BSD License',
			'Operating System :: POSIX',
			'Programming Language :: Python',
			'Topic :: System :: Installation/Setup'
		]
)
