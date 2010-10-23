#	vim:fileencoding=utf-8
# (c) 2010 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

import locale, os, subprocess, sys

from SmartLiveRebuild.output import out

class NonLiveEbuild(Exception):
	pass

class VCSSupport:
	reqenv = []
	optenv = []

	def __init__(self, cpv, bash, opts, settings):
		self.cpv = [cpv]
		self.env = bash(self.reqenv + self.optenv)
		self._opts = opts
		self._settings = settings
		self._running = False

		missingvars = [v for v in self.reqenv if self.env[v] == '']
		if len(missingvars) > 0:
			raise KeyError('Environment does not declare: %s' % missingvars)

	def __call__(self, blocking = False):
		if not self._running:
			self.startupdate()
			self._running = True
			if blocking:
				return self.endupdate(True)
			return None
		else:
			return self.endupdate()

	def getpath(self):
		raise NotImplementedError('VCS class needs to override getpath()')

	def append(self, vcs):
		if not isinstance(vcs, self.__class__):
			raise ValueError('Unable to append %s to %s' % (vcs.__class__, self.__class__))
		self.cpv.append(vcs.cpv[0])

	def getsavedrev(self):
		return None

	def getrev(self):
		raise NotImplementedError('VCS class needs to override getrev() or update()')

	@staticmethod
	def revcmp(oldrev, newrev):
		return oldrev == newrev

	@staticmethod
	def call(cmd, **kwargs):
		p = subprocess.Popen(cmd, stdout=subprocess.PIPE, **kwargs)
		ret = p.communicate()[0].decode(locale.getpreferredencoding(), 'replace')
		if p.wait() != 0:
			raise SystemError('Command failed: %s' % cmd)
		return ret

	def getupdatecmd(self):
		raise NotImplementedError('VCS class needs to override getupdatecmd()')

	def diffstat(self, oldrev, newrev):
		pass

	def startupdate(self):
		out.s2(str(self))
		os.chdir(self.getpath())
		self.oldrev = (not self._opts.local_rev and self.getsavedrev()) or self.getrev()

		if self._opts.network:
			cmd = self.getupdatecmd()
			out.s3(cmd)
			self.subprocess = subprocess.Popen(cmd, stdout=sys.stderr, shell=True)
		else:
			self.subprocess = None

		return self.subprocess

	def endupdate(self, blocking = False):
		if self.subprocess is None:
			ret = 0
		elif blocking:
			ret = self.subprocess.wait()
		else:
			ret = self.subprocess.poll()
			if ret is None:
				return None

		if ret == 0:
			os.chdir(self.getpath())
			newrev = self.getrev()
			if self._opts.jobs > 1:
				out.s2(str(self))

			if self.revcmp(self.oldrev, newrev):
				out.s3('at rev %s%s%s (no changes)' % (out.green, self.oldrev, out.reset))
				return False
			else:
				if self._opts.diffstat:
					self.diffstat(self.oldrev, newrev)
				out.s3('update from %s%s%s to %s%s%s' % (out.green, self.oldrev, out.reset, out.lime, newrev, out.reset))
				return True
		else:
			raise Exception('update command returned non-zero result')

	def abortupdate(self):
		if self._running and self.subprocess is not None:
			try:
				self.subprocess.terminate()
			except OSError:
				pass

	def __str__(self):
		return ', '.join(self.cpv)

vcs_cache = {}

def GetVCS(eclassname, allowed = []):
	if eclassname not in vcs_cache:
		if allowed and eclassname not in allowed:
			vcs_cache[eclassname] = None
		else:
			try:
				modname = 'SmartLiveRebuild.vcs.%s' % eclassname.replace('-', '_')
				vcs_cache[eclassname] = __import__(modname, globals(), locals(), ['myvcs']).myvcs
			except ImportError:
				vcs_cache[eclassname] = None

	return vcs_cache[eclassname]
