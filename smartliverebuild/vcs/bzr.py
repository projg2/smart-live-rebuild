#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

from smartliverebuild.vcs import RemoteVCSSupport, NonLiveEbuild

class BzrSupport(RemoteVCSSupport):
	reqenv = ['EBZR_REPO_URI', 'EBZR_REVNO', 'EBZR_REVNO_CMD']
	optenv = ['EBZR_REVISION']

	callenv = {'BZR_LOG': '/dev/null'}

	def __init__(self, *args, **kwargs):
		RemoteVCSSupport.__init__(self, *args, **kwargs)
		if self.env['EBZR_REVISION']:
			raise NonLiveEbuild('EBZR_REVISION set, package is not really a live one')

	def __str__(self):
		return self.env['EBZR_REPO_URI']

	def parseoutput(self, out):
		return int(out) if out else None

	@property
	def savedrev(self):
		rev = self.env['EBZR_REVNO']
		return self.parseoutput(rev)

	@staticmethod
	def revcmp(oldrev, newrev):
		return oldrev >= newrev

	@property
	def updatecmd(self):
		return '%s %s' % (self.env['EBZR_REVNO_CMD'], self.env['EBZR_REPO_URI'])
