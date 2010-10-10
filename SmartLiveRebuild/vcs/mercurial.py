#	vim:fileencoding=utf-8
# (c) 2010 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

import os.path, subprocess, sys
import portage

from SmartLiveRebuild.vcs import VCSSupport, NonLiveEbuild

class HgSupport(VCSSupport):
	reqenv = ['EHG_PROJECT', 'EHG_PULL_CMD', 'EHG_REPO_URI']
	optenv = ['EHG_REVISION', 'HG_REV_ID']

	trustopt = ['--config', 'trusted.users=portage']

	def __init__(self, *args):
		VCSSupport.__init__(self, *args)
		if self.env['EHG_REVISION'] and self.env['EHG_REVISION'] != 'tip':
			raise NonLiveEbuild('EHG_REVISION set, package is not really a live one')

	def getpath(self):
		dd = self._settings['PORTAGE_ACTUAL_DISTDIR'] or self._settings['DISTDIR']
		bn = os.path.basename(self.env['EHG_REPO_URI']) or os.path.basename(os.path.dirname(self.env['EHG_REPO_URI']))
		assert (bn != '')

		return '%s/hg-src/%s/%s' % (dd, self.env['EHG_PROJECT'], bn)

	def __str__(self):
		return self.env['EHG_REPO_URI'] or VCSSupport.__str__(self)

	def getsavedrev(self):
		return self.env['HG_REV_ID']

	def getrev(self):
		return self.call(['hg', 'tip', '--template', '{node}'] + self.trustopt)

	@staticmethod
	def revcmp(oldrev, newrev):
		return newrev.startswith(oldrev)

	def getupdatecmd(self):
		return ' '.join([self.env['EHG_PULL_CMD']] + self.trustopt)

	def diffstat(self, oldrev, newrev):
		subprocess.Popen(['hg', 'diff', '--stat', '-r', oldrev, '-r', newrev] + self.trustopt, stdout=sys.stderr).wait()

myvcs = HgSupport
