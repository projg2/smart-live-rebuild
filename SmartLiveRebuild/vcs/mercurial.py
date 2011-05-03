#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

import os.path

from SmartLiveRebuild.vcs import VCSSupport

class HgSupport(VCSSupport):
	reqenv = ['EHG_PROJECT', 'EHG_PULL_CMD', 'EHG_REPO_URI', 'EHG_REVISION']
	optenv = ['HG_REV_ID']

	trustopt = ['--config', 'trusted.users=portage']

	def getpath(self):
		dd = self._settings['PORTAGE_ACTUAL_DISTDIR'] or self._settings['DISTDIR']
		bn = os.path.basename(self.env['EHG_REPO_URI']) or os.path.basename(os.path.dirname(self.env['EHG_REPO_URI']))
		assert (bn != '')

		return '%s/hg-src/%s/%s' % (dd, self.env['EHG_PROJECT'], bn)

	def __str__(self):
		return self.env['EHG_REPO_URI']

	def getsavedrev(self):
		return self.env['HG_REV_ID']

	def getrev(self):
		return self.call(['hg', 'identify', '--id', '--rev', self.env['EHG_REVISION']]
				+ self.trustopt)

	@staticmethod
	def revcmp(oldrev, newrev):
		return newrev.startswith(oldrev)

	def getupdatecmd(self):
		return 'hg identify --id --rev %s %s %s' % (
				self.env['EHG_REVISION'], self.env['EHG_REPO_URI'],
				' '.join(self.trustopt))
