#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

import locale, os, subprocess
from gentoopm.util import ABCObject
from abc import abstractmethod, abstractproperty

from ..output import out

class NonLiveEbuild(Exception):
	""" A simple exception to be raised whenever the package is tied to
		a specific revision. This exception is catched within the core,
		and will not cause rebuild of the package. """
	pass

class BaseVCSSupport(ABCObject):
	""" Common VCS support class details. """
	_running = False

	@abstractproperty
	def reqenv(self):
		""" A list of obligatory environment variables necessary
			for the VCS to work. Their values will be grabbed
			by __init__(), and KeyError will be raised if any of them
			is unset.
		"""
		return []

	@property
	def optenv(self):
		""" A list of optional environment variables for the VCS.
			Their values will be grabbed by __init__(); if one is unset,
			an empty string will be used instead.
		"""
		return []

	@property
	def callenv(self):
		""" A dict of environment keys to set up when executing update
			command. By default, empty (meaning to wipe the env).
		"""
		return {}

	@property
	def cpv(self):
		""" A package ID for update requestor. """
		return self._cpv

	def __init__(self, cpv, environ, opts, cache = None):
		""" Initialize the VCS class for package `cpv', storing it as
			self.cpv. Get envvars from `environ' (self.reqenv + self.optenv).

			`opts' should point to an ConfigValues instance.

			When subclassing, the __init__() function is a good place
			to perform misc checks, like checking whether the package
			is actually a live ebuild and thus not tied to a specific
			revision.

			For this particular task, use a code like:

			def __init__(self, *args, **kwargs):
				VCSSupport.__init__(self, *args, **kwargs)
				if self.env['SOME_REVISION']:
					raise NonLiveEbuild('SOME_REVISION specifies revision, package is not really a live one')
		"""

		self._cpv = cpv
		self._opts = opts
		self._cache = cache
		self.env = environ.copy(*(self.reqenv + self.optenv))

		missingvars = [v for v in self.reqenv if not self.env[v]]
		if len(missingvars) > 0:
			raise KeyError('Environment does not declare: %s' % missingvars)

		class LazyHeader(object):
			def __init__(self, vcs):
				self._s = None
				self._vcs = vcs

			def __str__(self):
				if self._s is None:
					self._s = '[%s] %s' % (self._vcs.cpv, str(self._vcs))
				return self._s

		self._header = LazyHeader(self)

	@abstractmethod
	def __str__(self):
		pass

	@abstractproperty
	def updatecmd(self):
		""" The update command for a particular VCS as a shell
			command string.
		"""
		pass

	@abstractproperty
	def savedrev(self):
		""" The revision saved by the eclass whenever the package
			was built. This property should return the same type
			of information as .parseoutput() does, and should not rely
			on anything besides self.env.

			If you fail to grab the required information, return None.
		"""
		pass

	@staticmethod
	def revcmp(oldrev, newrev):
		""" A revision comparison function, appropriate
			for the particular type returned by getrev()
			and getsavedrev().

			This functions should return True if two revisions
			are equal (and thus no update is required), False otherwise.
		"""
		return oldrev == newrev

	# -- private --

	def __call__(self, blocking = False):
		""" Perform a single main loop iteration. """
		if not self._running:
			rev = self._cache.get(str(self)) if self._cache is not None else None

			if rev is None:
				self._startupdate()
				self._running = True
				if blocking:
					return self._endupdate(True)
				return None
			elif isinstance(rev, Exception):
				raise rev
			elif isinstance(rev, BaseVCSSupport):
				# wait for it to complete, and cache its result
				return None
			else:
				return self._finishupdate(rev)
		else:
			return self._endupdate()

	def _startupdate(self, popenargs = {}):
		""" Start the update process. Grabs the current revision
			via .savedrev, grabs the update command (.updatecmd)
			and executes it in the background using subprocess.Popen().

			The spawned command is supposed to return the new revision
			on STDOUT, and any diagnostic messages on STDERR.
			If necessary, shell output redirection (`>&2') can be used
			to clean up STDOUT.

			This function returns the spawned Popen() instance.
		"""

		if self._cache is not None:
			self._cache[str(self)] = self

		cmd = self.updatecmd
		if self._opts.jobs > 1:
			out.pkgs(str(self), cmd)
		else:
			out.pkgs(self._header, cmd)

		popenargs['env'] = self.callenv
		popenargs['shell'] = True
		self.subprocess = subprocess.Popen(cmd, **popenargs)

		return self.subprocess

	def _endupdate(self, blocking = False):
		""" Depending on whether `blocking' is True, either wait
			for update process termination or check whether it is done.
			In the latter case, return None if the process is still
			running.

			If the update command terminates successfully, this method
			grabs the new working tree revision, compares it to the old
			one and returns the comparison result as a boolean.

			In other words, if the revision changed (and thus package
			needs to be rebuilt), this method returns True. Otherwise,
			it returns False.
		"""

		if not blocking:
			# let's hope we don't get much output
			ret = self.subprocess.poll()
			if ret is None:
				return None

		(sod, sed) = self.subprocess.communicate()
		ret = self.subprocess.returncode
		self._running = False

		if ret == 0:
			newrev = self.parseoutput(sod.decode('ASCII') if sod else '')
			if newrev is None:
				raise Exception('update command failed to return a rev')

			if self._cache is not None:
				self._cache[str(self)] = newrev
			return self._finishupdate(newrev)
		else:
			raise Exception('update command returned non-zero result')

	def _finishupdate(self, newrev):
		oldrev = self.savedrev
		if self.revcmp(oldrev, newrev):
			out.pkgs(self._header, 'at rev %s%s%s (no changes)' % \
					(out.green, oldrev, out.reset))
			return False
		else:
			out.pkgs(self._header, 'update from %s%s%s to %s%s%s' % \
					(out.green, oldrev, out.reset, out.lime, newrev, out.reset))
			return True

	def __del__(self):
		""" Terminate the running update subprocess if appropriate. """
		if self._running and self.subprocess is not None:
			try:
				self.subprocess.terminate()
			except OSError:
				pass

class RemoteVCSSupport(BaseVCSSupport):
	""" A base class for remote-capable VCS implementations. In other
		words, those VCS-es which can handle checking for updates using
		network and ebuild environment variables only, without the need
		for a checkout. """

	def parseoutput(self, out):
		""" Parse output from updatecmd and return a revision.
			By default, simply passes the output on. """
		return out

	def _startupdate(self):
		BaseVCSSupport._startupdate(self, \
				popenargs = {'stdout': subprocess.PIPE})

class CheckoutVCSSupport(BaseVCSSupport):
	""" A base class for VCS implementations requiring a checkout. """

	@abstractproperty
	def workdir(self):
		""" The absolute path to the checkout directory. The program
			will enter that particular directory before executing
			the update command or getting the checked out revision.
		"""
		pass

	@abstractproperty
	def currentrev(self):
		""" The current revision work tree revision. """
		pass

	def _startupdate(self):
		""" Start the update command in the checkout directory. """
		os.chdir(self.workdir)
		BaseVCSSupport._startupdate(self)

	def parseoutput(self, output):
		""" Fake parsing the output by grabbing revision from the work
			tree.
		"""
		os.chdir(self.workdir)
		return self.currentrev

	def call(self, cmd, **kwargs):
		""" A helper method for VCS classes. It executes the process
			passed as `cmd' (in the form of a list), grabs it output
			and returns it.

			By default, STDERR is not captured (and thus is output to
			screen), and the process is called with environment updated
			from self.callenv. Additional keyword arguments will be
			passed to subprocess.Popen().
		"""
		env = self.callenv.copy()
		if 'env' in kwargs:
			env.update(kwargs['env'])
		newkwargs = kwargs.copy()
		newkwargs['env'] = env

		p = subprocess.Popen(cmd, stdout=subprocess.PIPE, **newkwargs)
		ret = p.communicate()[0].decode(locale.getpreferredencoding(), 'replace')
		if p.wait() != 0:
			raise SystemError('Command failed: %s' % cmd)
		return ret
