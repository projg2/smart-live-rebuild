#!/usr/bin/python
#	vim:fileencoding=utf-8:noet
# (c) 2011-2022 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

from setuptools import setup, Command

import os.path, sys

sys.path.insert(0, os.path.dirname(__file__))
try:
	from smartliverebuild import PV
except ImportError:
	PV = 'unknown'

class TestCommand(Command):
	user_options = []

	def initialize_options(self):
		pass

	def finalize_options(self):
		pass

	def run(self):
		import unittest, doctest

		tests = unittest.TestSuite()
		tests.addTests(doctest.DocTestSuite('smartliverebuild.filtering'))

		r = unittest.TextTestRunner()
		res = r.run(tests)
		sys.exit(0 if res.wasSuccessful() else 1)

setup(
		name = 'smart-live-rebuild',
		version = PV,
		author = 'Michał Górny',
		author_email = 'mgorny@gentoo.org',
		url = 'http://github.com/mgorny/smart-live-rebuild',

		packages = ['smartliverebuild', 'smartliverebuild.vcs'],
		entry_points={
			'console_scripts': [
				'smart-live-rebuild=smartliverebuild.cli:setuptools_main',
			],
		},

		classifiers = [
			'Development Status :: 5 - Production/Stable',
			'Environment :: Console',
			'Environment :: Plugins',
			'Intended Audience :: System Administrators',
			'License :: OSI Approved :: BSD License',
			'Operating System :: POSIX',
			'Programming Language :: Python',
			'Topic :: System :: Installation/Setup'
		],

		cmdclass = {
			'test': TestCommand
		}
)
