#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

from smartliverebuild.vcs import VCSSupport, NonLiveEbuild

class GitSupport(VCSSupport):
	reqenv = ['EGIT_BRANCH', 'EGIT_REPO_URI', 'EGIT_VERSION']
	optenv = ['EGIT_COMMIT']

	def __init__(self, *args):
		VCSSupport.__init__(self, *args)
		if self.env['EGIT_COMMIT'] and self.env['EGIT_COMMIT'] != self.env['EGIT_BRANCH']:
			raise NonLiveEbuild('EGIT_COMMIT set, package is not really a live one')

	def __str__(self):
		return self.env['EGIT_REPO_URI']

	def parseoutput(self, out):
		return out.split()[0]

	def getsavedrev(self):
		return self.env['EGIT_VERSION']

	def getupdatecmd(self):
		return 'git ls-remote --heads %s %s' % (
				self.env['EGIT_REPO_URI'], self.env['EGIT_BRANCH'])
