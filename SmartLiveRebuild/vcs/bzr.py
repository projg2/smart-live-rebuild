#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

from SmartLiveRebuild.vcs import VCSSupport, NonLiveEbuild

class BzrSupport(VCSSupport):
	reqenv = ['EBZR_REPO_URI', 'EBZR_REVNO_CMD', 'EBZR_UPDATE_CMD', 'EBZR_WC_PATH']
	optenv = ['EBZR_OPTIONS', 'EBZR_REVISION', 'EBZR_REVNO']

	def __init__(self, *args):
		VCSSupport.__init__(self, *args)
		if self.env['EBZR_REVISION']:
			raise NonLiveEbuild('EBZR_REVISION set, package is not really a live one')
		self.callenv['BZR_LOG'] = '/dev/null'

	def getpath(self):
		return self.env['EBZR_WC_PATH']

	def __str__(self):
		return self.env['EBZR_REPO_URI']

	def parseoutput(self, out):
		return int(out) if out else None

	def getrev(self):
		rev = self.call(self.env['EBZR_REVNO_CMD'].split())
		return self.parseoutput(rev)

	def getsavedrev(self):
		rev = self.env['EBZR_REVNO']
		return self.parseoutput(rev)

	def revcmp(self, oldrev, newrev):
		return oldrev >= newrev

	def getupdatecmd(self):
		return '%s %s' % (self.env['EBZR_REVNO_CMD'], self.env['EBZR_REPO_URI'])
