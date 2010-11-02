#	vim:fileencoding=utf-8
# (c) 2010 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

import subprocess, sys, re

from SmartLiveRebuild.vcs import VCSSupport

class DarcsSupport(VCSSupport):
	reqenv = ['EDARCS_REPOSITORY', 'EDARCS_GET_CMD', 'EDARCS_UPDATE_CMD',
			'EDARCS_LOCALREPO', 'EDARCS_TOP_DIR', 'EDARCS_OPTIONS',
			'EDARCS_DARCS_CMD']
	optenv = ['EDARCS_PATCHCOUNT']

	def getpath(self):
		return '%s/%s' \
			% (self.env['EDARCS_TOP_DIR'], self.env['EDARCS_LOCALREPO'])

	def __str__(self):
		return self.env['EDARCS_REPOSITORY'] or VCSSupport.__str__(self)

	def getrev(self):
		result = self.call(['darcs', 'show', 'repo'])
		return int(re.search('Num Patches: ([0-9]+)', result).group(1))

	def getsavedrev(self):
		pc = self.env['EDARCS_PATCHCOUNT']
		return int(pc) if pc else None

	@staticmethod
	def revcmp(oldrev, newrev):
		return oldrev == newrev

	def getupdatecmd(self):
		# darcs trying to close stderr as cvs does
		# see SmartLiveRebuild/vcs/cvs.py for comments
		return '%s %s --all %s %s 2>&1' % \
			(self.env['EDARCS_DARCS_CMD'],
			self.env['EDARCS_UPDATE_CMD'],
			self.env['EDARCS_OPTIONS'],
			self.env['EDARCS_REPOSITORY'])

	def diffstat(self, oldrev, newrev):
		subprocess.Popen(['darcs', 'chan', '--last', newrev - oldrev],
				stdout=sys.stderr).wait()
