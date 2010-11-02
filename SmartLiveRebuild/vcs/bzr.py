#	vim:fileencoding=utf-8
# (c) 2010 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

import codecs

from SmartLiveRebuild.vcs import VCSSupport, NonLiveEbuild

class BzrSupport(VCSSupport):
	reqenv = ['EBZR_CACHE_DIR', 'EBZR_STORE_DIR', 'EBZR_UPDATE_CMD']
	optenv = ['EBZR_OPTIONS', 'EBZR_REPO_URI', 'EBZR_REVISION', 'EBZR_TREE_CRC32']

	def __init__(self, *args):
		VCSSupport.__init__(self, *args)
		if self.env['EBZR_REVISION']:
			raise NonLiveEbuild('EBZR_REVISION set, package is not really a live one')
		self.callenv['BZR_LOG'] = '/dev/null'

	def getpath(self):
		return '%s/%s' % (self.env['EBZR_STORE_DIR'], self.env['EBZR_CACHE_DIR'])

	def __str__(self):
		return self.env['EBZR_REPO_URI'] or VCSSupport.__str__(self)

	# bzr revno requires network interaction, so we just use the checksum.
	def getrev(self):
		inp = codecs.open('%s/.bzr/checkout/dirstate' % self.getpath(), 'r', 'utf8', 'ignore')
		for l in inp:
			lf = l.split(None, 3)
			if lf[0] == 'crc32:':
				inp.close()
				return int(lf[1])
		else:
			inp.close()
			raise ValueError('Unable to find crc32 in .bzr/checkout/dirstate')

	def getsavedrev(self):
		crc = self.env['EBZR_TREE_CRC32']
		return int(crc) if crc else None

	@staticmethod
	def revcmp(oldrev, newrev):
		return oldrev == newrev

	def getupdatecmd(self):
		return '%s %s' % (self.env['EBZR_UPDATE_CMD'], self.env['EBZR_OPTIONS'])
