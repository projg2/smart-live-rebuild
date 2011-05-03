#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

import re

from SmartLiveRebuild.vcs import VCSSupport, NonLiveEbuild

class SvnSupport(VCSSupport):
	reqenv = ['ESVN_STORE_DIR', 'ESVN_REPO_URI']
	optenv = ['ESVN_REVISION', 'ESVN_WC_PATH', 'ESVN_WC_REVISION']

	revre = re.compile('(?m)^Last Changed Rev: (\d+)$')

	def __init__(self, *args):
		VCSSupport.__init__(self, *args)
		if self.env['ESVN_REPO_URI'] and self.env['ESVN_REPO_URI'].find('@') != -1:
			raise NonLiveEbuild('ESVN_REPO_URI specifies revision, package is not really a live one')
		elif self.env['ESVN_REVISION']:
			raise NonLiveEbuild('ESVN_REVISION set, package is not really a live one')
		elif not self.env['ESVN_WC_PATH']:
			raise KeyError('Environment does not declare ESVN_WC_PATH while the package is a live one')
		self.callenv['LC_ALL'] = 'C'

	def getpath(self):
		return self.env['ESVN_WC_PATH']

	def __str__(self):
		return self.env['ESVN_REPO_URI']

	def parseoutput(self, out):
		m = self.revre.search(out)
		return int(m.group(1)) if m is not None else None

	def getsavedrev(self):
		return int(self.env['ESVN_WC_REVISION'])

	def getrev(self):
		svninfo = self.call(['svn', '--config-dir', '%s/.subversion' % \
				self.env['ESVN_STORE_DIR'], 'info'])
		m = self.revre.search(svninfo)
		return int(m.group(1)) if m is not None else None

	@staticmethod
	def revcmp(oldrev, newrev):
		return oldrev >= newrev

	def getupdatecmd(self):
		# XXX: branch?
		return 'svn --config-dir %s/.subversion info %s' % (
			self.env['ESVN_STORE_DIR'], self.env['ESVN_REPO_URI'])
