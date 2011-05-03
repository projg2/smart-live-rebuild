#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

from SmartLiveRebuild.vcs import VCSSupport, NonLiveEbuild

class GitSupport(VCSSupport):
	reqenv = ['EGIT_BRANCH', 'EGIT_PROJECT', 'EGIT_REPO_URI', 'EGIT_STORE_DIR']
	optenv = ['EGIT_COMMIT', 'EGIT_DIFFSTAT_CMD', 'EGIT_HAS_SUBMODULES', 'EGIT_VERSION']

	def __init__(self, *args):
		VCSSupport.__init__(self, *args)
		if self.env['EGIT_COMMIT'] and self.env['EGIT_COMMIT'] != self.env['EGIT_BRANCH']:
			raise NonLiveEbuild('EGIT_COMMIT set, package is not really a live one')

	def getpath(self):
		return '%s/%s' % (self.env['EGIT_STORE_DIR'], self.env['EGIT_PROJECT'])

	def __str__(self):
		return self.env['EGIT_REPO_URI']

	def parseoutput(self, out):
		return out.split()[0]

	def getsavedrev(self):
		return self.env['EGIT_VERSION']

	def getrev(self):
		branch = self.env['EGIT_BRANCH']
		if self.env['EGIT_HAS_SUBMODULES']:
			branch = 'origin/%s' % branch
		return self.call(['git', 'rev-parse', branch]).split('\n')[0]

	def getupdatecmd(self):
		return 'git ls-remote --heads %s %s' % (
				self.env['EGIT_REPO_URI'], self.env['EGIT_BRANCH'])
