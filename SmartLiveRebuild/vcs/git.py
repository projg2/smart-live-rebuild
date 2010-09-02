#	vim:fileencoding=utf-8
# (c) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

import subprocess, sys

from SmartLiveRebuild.vcs import VCSSupport, NonLiveEbuild

class GitSupport(VCSSupport):
	reqenv = ['EGIT_BRANCH', 'EGIT_PROJECT', 'EGIT_STORE_DIR', 'EGIT_UPDATE_CMD']
	optenv = ['EGIT_COMMIT', 'EGIT_DIFFSTAT_CMD', 'EGIT_HAS_SUBMODULES', 'EGIT_OPTIONS', 'EGIT_REPO_URI', 'EGIT_VERSION']

	def __init__(self, *args):
		VCSSupport.__init__(self, *args)
		if self.env['EGIT_COMMIT'] and self.env['EGIT_COMMIT'] != self.env['EGIT_BRANCH']:
			raise NonLiveEbuild('EGIT_COMMIT set, package is not really a live one')

	def getpath(self):
		return '%s/%s' % (self.env['EGIT_STORE_DIR'], self.env['EGIT_PROJECT'])

	def __str__(self):
		return self.env['EGIT_REPO_URI'] or VCSSupport.__str__(self)

	def getsavedrev(self):
		return self.env['EGIT_VERSION']

	def getrev(self):
		branch = self.env['EGIT_BRANCH']
		if self.env['EGIT_HAS_SUBMODULES']:
			branch = 'origin/%s' % branch
		return self.call(['git', 'rev-parse', branch]).split('\n')[0]

	def getupdatecmd(self):
		if self.env['EGIT_HAS_SUBMODULES']:
			return '%s %s' % (self.env['EGIT_UPDATE_CMD'], self.env['EGIT_OPTIONS'])
		else:
			return '%s %s origin %s:%s' % (self.env['EGIT_UPDATE_CMD'], self.env['EGIT_OPTIONS'], self.env['EGIT_BRANCH'], self.env['EGIT_BRANCH'])

	def diffstat(self, oldrev, newrev):
		subprocess.Popen('%s %s..%s' % (self.env['EGIT_DIFFSTAT_CMD'] or 'git diff', oldrev, newrev), stdout=sys.stderr, shell=True).wait()

myvcs = GitSupport
