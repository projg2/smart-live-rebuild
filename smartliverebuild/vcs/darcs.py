#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

import re

from smartliverebuild.vcs import CheckoutVCSSupport

class DarcsSupport(CheckoutVCSSupport):
	reqenv = ['EDARCS_REPOSITORY', 'EDARCS_GET_CMD', 'EDARCS_UPDATE_CMD',
			'EDARCS_LOCALREPO', 'EDARCS_TOP_DIR', 'EDARCS_OPTIONS',
			'EDARCS_DARCS_CMD']
	optenv = ['EDARCS_PATCHCOUNT']

	@property
	def workdir(self):
		return '%s/%s' \
			% (self.env['EDARCS_TOP_DIR'], self.env['EDARCS_LOCALREPO'])

	def __str__(self):
		return self.env['EDARCS_REPOSITORY']

	@property
	def currentrev(self):
		result = self.call(['darcs', 'show', 'repo'])
		return int(re.search('Num Patches: ([0-9]+)', result).group(1))

	@property
	def savedrev(self):
		pc = self.env['EDARCS_PATCHCOUNT']
		return int(pc) if pc else None

	@property
	def updatecmd(self):
		return '%s %s --all %s %s >&2' % \
			(self.env['EDARCS_DARCS_CMD'],
			self.env['EDARCS_UPDATE_CMD'],
			self.env['EDARCS_OPTIONS'],
			self.env['EDARCS_REPOSITORY'])
