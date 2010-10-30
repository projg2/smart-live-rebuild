#	vim:fileencoding=utf-8
# (c) 2010 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

from SmartLiveRebuild.vcs import VCSSupport, NonLiveEbuild

class BzrSupport(VCSSupport):
	reqenv = ['EBZR_CACHE_DIR', 'EBZR_REVNO_CMD', 'EBZR_STORE_DIR', 'EBZR_UPDATE_CMD']
	optenv = ['EBZR_OPTIONS', 'EBZR_REPO_URI', 'EBZR_REVISION']

	callenv = {
		'BZR_LOG': '/dev/null'
	}

	def __init__(self, *args):
		VCSSupport.__init__(self, *args)
		if self.env['EBZR_REVISION']:
			raise NonLiveEbuild('EBZR_REVISION set, package is not really a live one')

	def getpath(self):
		return '%s/%s' % (self.env['EBZR_STORE_DIR'], self.env['EBZR_CACHE_DIR'])

	def __str__(self):
		return self.env['EBZR_REPO_URI'] or VCSSupport.__str__(self)

	def getrev(self):
		ret = self.call(self.env['EBZR_REVNO_CMD'].split(),
				stderr = open('/dev/null', 'w')).strip()
		return ret

	@staticmethod
	def revcmp(oldrev, newrev):
		return newrev.startswith(oldrev)

	def getupdatecmd(self):
		return '%s %s' % (self.env['EBZR_UPDATE_CMD'], self.env['EBZR_OPTIONS'])

myvcs = BzrSupport
