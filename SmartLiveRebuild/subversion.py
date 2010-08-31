import re

from SmartLiveRebuild.vcs import VCSSupport, NonLiveEbuild

class SvnSupport(VCSSupport):
	inherit = 'subversion'
	reqenv = ['ESVN_STORE_DIR', 'ESVN_UPDATE_CMD', 'ESVN_WC_PATH']
	optenv = ['ESVN_REVISION', 'ESVN_OPTIONS', 'ESVN_PASSWORD', 'ESVN_REPO_URI', 'ESVN_USER', 'ESVN_WC_REVISION']

	revre = re.compile('(?m)^Last Changed Rev: (\d+)$')

	def __init__(self, *args):
		VCSSupport.__init__(self, *args)
		if self.env['ESVN_REPO_URI'] and self.env['ESVN_REPO_URI'].find('@') != -1:
			raise NonLiveEbuild('ESVN_REPO_URI specifies revision, package is not really a live one')
		elif self.env['ESVN_REVISION']:
			raise NonLiveEbuild('ESVN_REVISION set, package is not really a live one')

	def getpath(self):
		return self.env['ESVN_WC_PATH']

	def __str__(self):
		return self.env['ESVN_REPO_URI'] or VCSSupport.__str__(self)

	def getsavedrev(self):
		return self.env['ESVN_WC_REVISION']

	def getrev(self):
		svninfo = self.call(['svn', '--config-dir', '%s/.subversion' % self.env['ESVN_STORE_DIR'], 'info'])
		m = self.revre.search(svninfo)
		return m.group(1) if m is not None else None

	@staticmethod
	def revcmp(oldrev, newrev):
		return oldrev >= newrev

	def getupdatecmd(self):
		cmd = '%s %s --config-dir %s/.subversion' % (self.env['ESVN_UPDATE_CMD'], self.env['ESVN_OPTIONS'], self.env['ESVN_STORE_DIR'])
		if self.env['ESVN_USER']:
			cmd += ' --user "%s" --password "%s"' % (self.env['ESVN_USER'], self.env['ESVN_PASSWORD'])
		return cmd
