#	vim:fileencoding=utf-8
# (c) 2010 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

import subprocess, sys, re

from SmartLiveRebuild.vcs import VCSSupport

class DarcsSupport(VCSSupport):
	reqenv = ['EDARCS_REPOSITORY', 'EDARCS_GET_CMD', 'EDARCS_UPDATE_CMD', 
			'EDARCS_LOCALREPO','EDARCS_TOP_DIR','EDARCS_OPTIONS','EDARCS_DARCS_CMD']

	def __init__(self, *args):
		VCSSupport.__init__(self, *args)

	def getpath(self):
		return '%s/%s/' \
			% (self.env['EDARCS_TOP_DIR'], self.env['EDARCS_LOCALREPO'])

	def __str__(self):
		return self.env['EDARCS_REPOSITORY'] or VCSSupport.__str__(self)

	def getsavedrev(self):
		return self.getrev()

	def getrev(self):
		result = self.call(['darcs', 'show', 'repo'])
		return re.search('Num Patches: ([0-9]+)', result).group(1)

	@staticmethod
	def revcmp(oldrev, newrev):
		return int(oldrev)==int(newrev)

	def getupdatecmd(self):
		return '%s %s --all %s %s' % (self.env['EDARCS_DARCS_CMD'],
			self.env['EDARCS_UPDATE_CMD'], 
			self.env['EDARCS_OPTIONS'],    
			self.env['EDARCS_REPOSITORY'])

	def diffstat(self, oldrev, newrev):
		subprocess.Popen('%s %s' % ('darcs chan --last', int(newrev)-int(oldrev)), stdout=sys.stderr, shell=True).wait()

myvcs = DarcsSupport
