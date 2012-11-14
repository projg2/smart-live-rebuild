#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

import re

from . import RemoteVCSSupport, NonLiveEbuild

class SubversionSupport(RemoteVCSSupport):
	reqenv = ['ESVN_REPO_URI', 'ESVN_STORE_DIR', 'ESVN_WC_REVISION']
	optenv = ['ESVN_REVISION']

	revre = re.compile('(?m)^Last Changed Rev: (\d+)$')

	@property
	def callenv(self):
		env = RemoteVCSSupport.callenv.fget(self).copy()
		env.update({'LC_ALL': 'C'})
		return env

	def __init__(self, *args, **kwargs):
		RemoteVCSSupport.__init__(self, *args, **kwargs)
		if self.env['ESVN_REPO_URI'] and self.env['ESVN_REPO_URI'].find('@') != -1:
			raise NonLiveEbuild('ESVN_REPO_URI specifies revision, package is not really a live one')
		elif self.env['ESVN_REVISION']:
			raise NonLiveEbuild('ESVN_REVISION set, package is not really a live one')

	def __str__(self):
		return self.env['ESVN_REPO_URI']

	def parseoutput(self, out):
		m = self.revre.search(out)
		return int(m.group(1)) if m is not None else None

	@property
	def savedrev(self):
		return int(self.env['ESVN_WC_REVISION'])

	@staticmethod
	def revcmp(oldrev, newrev):
		return oldrev >= newrev

	@property
	def updatecmd(self):
		# XXX: branch?
		return 'svn --config-dir %s/.subversion info %s' % (
			self.env['ESVN_STORE_DIR'], self.env['ESVN_REPO_URI'])
