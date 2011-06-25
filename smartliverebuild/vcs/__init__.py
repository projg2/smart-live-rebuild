#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

import locale, os, subprocess
from abc import ABCMeta, abstractproperty

from smartliverebuild.output import out

class NonLiveEbuild(Exception):
	""" A simple exception to be raised whenever the package is tied to
		a specific revision. This exception is catched within the core,
		and will not cause rebuild of the package. """
	pass

class RemoteVCSSupport(object):
	""" A base class for remote-capable VCS implementations. In other
		words, those VCS-es which can handle checking for updates using
		network and ebuild environment variables only, without the need
		for a checkout. """
	__metaclass__ = ABCMeta

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
		""" A list of CPVs which use this particular repository. """
		return self._cpv

	def __init__(self, cpv, bash, opts, settings):
		""" Initialize the VCS class for package `cpv', storing it as
			self.cpv. Call `bash' BashParser instance to get the values
			for environment variables (self.reqenv + self.optenv).

			`opts' should point to an ConfigValues instance, while
			`settings' to the portage settings instance.
			
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

		self._cpv = [cpv]
		self.env = bash(self.reqenv + self.optenv)
		self._opts = opts
		self._settings = settings
		self._running = False

		missingvars = [v for v in self.reqenv if self.env[v] == '']
		if len(missingvars) > 0:
			raise KeyError('Environment does not declare: %s' % missingvars)

	def __str__(self):
		""" Return the string used to identify the update process within
			the program output.
		"""
		return ', '.join(self.cpv)

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

	def parseoutput(self, out):
		""" Parse output from updatecmd and return a revision.
			By default, simply passes the output on. """
		return out

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
			self.startupdate()
			self._running = True
			if blocking:
				return self.endupdate(True)
			return None
		else:
			return self.endupdate()

	def startupdate(self):
		""" Start the update process. Grabs the current revision
			via .savedrev, grabs the update command (.updatecmd)
			and executes it in the background using subprocess.Popen().

			The spawned command is supposed to return the new revision
			on STDOUT, and any diagnostic messages on STDERR.
			If necessary, shell output redirection (`>&2') can be used
			to clean up STDOUT.

			This function returns the spawned Popen() instance.
		"""

		self.oldrev = self.savedrev

		cmd = self.updatecmd
		out.s2(str(self))
		out.s3(cmd)
		self.subprocess = subprocess.Popen(cmd, stdout=subprocess.PIPE,
				env=self.callenv, shell=True)

		return self.subprocess

	def endupdate(self, blocking = False):
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
			newrev = self.parseoutput(sod.decode('ASCII'))

			if newrev is None:
				raise Exception('update command failed to return a rev')
			if self._opts.jobs > 1:
				out.s2(str(self))

			if self.revcmp(self.oldrev, newrev):
				out.s3('at rev %s%s%s (no changes)' % (out.green, self.oldrev, out.reset))
				return False
			else:
				out.s3('update from %s%s%s to %s%s%s' % (out.green, self.oldrev, out.reset, out.lime, newrev, out.reset))
				return True
		else:
			raise Exception('update command returned non-zero result')

	def abortupdate(self):
		""" Terminate the running update subprocess if appropriate. """
		if self._running and self.subprocess is not None:
			try:
				self.subprocess.terminate()
			except OSError:
				pass

class VCSSupport:
	""" A base class for all VCS implementations, and which all VCS
		classes	should subclass, overriding appropriate methods
		and attributes.

		Subclasses should override reqenv and optenv in the first place.
		These are iterables of environment variable names, which are
		supposed to be grabbed from within the environment.bz2 file.

		The reqenv attribute represents the obligatory variables; in
		other words, a KeyError will be raised if any of them is unset.

		The optenv attribute represents the optional variables; if one
		of them is unset, an empty value will be used instead.

		The callenv dictionary represents common environment variables
		which are supposed to be set during subprocess execution.
		The subclasses should append to this dictionary instead of
		overriding it completely.
	"""
	reqenv = []
	optenv = []

	callenv = {}

	requires_workdir = False

	def __init__(self, cpv, bash, opts, settings):
		""" Initialize the VCS class for package `cpv', storing it as
			self.cpv. Call `bash' BashParser instance to get the values
			for environment variables (self.reqenv + self.optenv).

			`opts' should point to an ConfigValues instance, while
			`settings' to the portage settings instance.
			
			When subclassing, the __init__() function is a good place to
			perform misc checks, like checking whether the package is
			actually a live ebuild and thus not tied to a specific
			revision.

			For this particular task, use a code like below:

			def __init__(self, *args):
				VCSSupport.__init__(self, *args)
				if self.env['SOME_REVISION']:
					raise NonLiveEbuild('SOME_REVISION specifies revision, package is not really a live one')
		"""
			
		self.cpv = [cpv]
		self.env = bash(self.reqenv + self.optenv)
		self._opts = opts
		self._settings = settings
		self._running = False

		missingvars = [v for v in self.reqenv if self.env[v] == '']
		if len(missingvars) > 0:
			raise KeyError('Environment does not declare: %s' % missingvars)

	def __call__(self, blocking = False):
		""" Perform a single main loop iteration. """
		if not self._running:
			self.startupdate()
			self._running = True
			if blocking:
				return self.endupdate(True)
			return None
		else:
			return self.endupdate()

	def getpath(self):
		""" Get the absolute path to the checkout directory. The program
			will enter that particular directory before executing
			the update command or calling one of the following methods:
			- getrev().
		"""
		raise NotImplementedError('VCS class needs to override getpath()')

	def append(self, vcs):
		""" Append the additional packages from another VCS class
			instance `vcs'. This will be done whenever two packages
			share the same checkout directory (as returned by getpath()).
		"""
		if not isinstance(vcs, self.__class__):
			raise ValueError('Unable to append %s to %s' % (vcs.__class__, self.__class__))
		self.cpv.append(vcs.cpv[0])

	def getsavedrev(self):
		""" Return the revision saved by the eclass whenever the package
			was built. This method should return the same type
			of information as getrev() does, and should not rely on
			anything besides self.env.

			If a particular VCS eclass doesn't provide such
			an information, don't override this method. If you fail to
			grab the required information, return None.
		"""
		return None

	def getrev(self):
		""" Grab the revision from the work tree. """
		raise NotImplementedError('VCS class needs to override getrev() or update()')

	def parseoutput(self, out):
		""" Parse output from updatecmd and return a revision. """
		return out

	@staticmethod
	def revcmp(oldrev, newrev):
		""" A revision comparison function, appropriate
			for the particular type returned by getrev()
			and getsavedrev().

			This functions should return True if two revisions
			are equal (and thus no update is required), False otherwise.
		"""
		return oldrev == newrev

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

	def getupdatecmd(self):
		""" Return the update command for a particular VCS as a shell
			command string. It will be executed within the checkout
			directory, as returned by self.getpath().
		"""
		raise NotImplementedError('VCS class needs to override getupdatecmd()')

	def startupdate(self):
		""" Start the update process. Grabs the current revision from
			the checkout (or getsavedrev()), grabs the update command
			(self.getupdatecmd()) and executes it in the background
			using subprocess.Popen().

			The spawned command is supposed to return the new revision
			on STDOUT, and any diagnostic messages on STDERR.
			If necessary, shell output redirection (`>&2') can be used
			to clean up STDOUT.

			This function returns the spawned Popen() instance.
		"""

		if self.requires_workdir:
			os.chdir(self.getpath())
		self.oldrev = self.getsavedrev()

		cmd = self.getupdatecmd()
		out.s2(str(self))
		out.s3(cmd)
		self.subprocess = subprocess.Popen(cmd, stdout=subprocess.PIPE,
				env=self.callenv, shell=True)
		self.stdoutbuf = ''

		return self.subprocess

	def endupdate(self, blocking = False):
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

		if ret == 0:
			newrev = self.parseoutput(sod.decode('ASCII'))

			if newrev is None:
				if self.requires_workdir:
					os.chdir(self.getpath())
					newrev = self.getrev()
				else:
					raise Exception('update command failed to return a rev')
			if self._opts.jobs > 1:
				out.s2(str(self))

			if self.revcmp(self.oldrev, newrev):
				out.s3('at rev %s%s%s (no changes)' % (out.green, self.oldrev, out.reset))
				return False
			else:
				out.s3('update from %s%s%s to %s%s%s' % (out.green, self.oldrev, out.reset, out.lime, newrev, out.reset))
				return True
		else:
			raise Exception('update command returned non-zero result')

	def abortupdate(self):
		""" Terminate the running update subprocess if appropriate. """
		if self._running and self.subprocess is not None:
			try:
				self.subprocess.terminate()
			except OSError:
				pass

	def __str__(self):
		""" Return the string used to identify the update process within
			the program output.
		"""
		return ', '.join(self.cpv)
