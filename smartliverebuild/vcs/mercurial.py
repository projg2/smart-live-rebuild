#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

from . import RemoteVCSSupport, NonLiveEbuild

class MercurialSupport(RemoteVCSSupport):
	reqenv = ['EHG_REPO_URI', 'EHG_REVISION', 'HG_REV_ID']

	trustopt = ['--config', 'trusted.users=portage'] # XXX: pm.config.userpriv_uid

	def __init__(self, *args, **kwargs):
		RemoteVCSSupport.__init__(self, *args, **kwargs)
		if self.revcmp(self.savedrev, self.env['EHG_REVISION']):
			raise NonLiveEbuild('EHG_REVISION set to a revision, package is not really a live one')

	def __str__(self):
		return self.env['EHG_REPO_URI']

	@property
	def savedrev(self):
		return self.env['HG_REV_ID']

	@staticmethod
	def revcmp(oldrev, newrev):
		# assume either can be longer
		return newrev.startswith(oldrev) or oldrev.startswith(newrev)

	@property
	def updatecmd(self):
		return 'hg identify --id --rev %s %s %s' % (
				self.env['EHG_REVISION'], self.env['EHG_REPO_URI'],
				' '.join(self.trustopt))
