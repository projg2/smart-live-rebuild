#	vim:fileencoding=utf-8
# (c) 2010 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

import locale, os, subprocess, sys

from SmartLiveRebuild.output import out

class NonLiveEbuild(Exception):
	""" A simple exception to be raised whenever the package is tied to
		a specific revision. This exception is catched within the core,
		and will not cause rebuild of the package. """
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
			- getrev(),
			- diffstat().
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

	def getremoterev(self):
		""" Return the revision given by the remote server without
			touching the working copy.
		"""
		return None

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

	def diffstat(self, oldrev, newrev):
		""" Execute the 'diffstat' command, summarizing the changes
			between revisions `oldrev' and `newrev'.

			If the VCS doesn't provide a standard diffstat command,
			don't override this method.
		"""
		pass

	def startupdate(self):
		""" Start the update process. Grabs the current revision from
			the checkout (or getsavedrev()), grabs the update command
			(self.getupdatecmd()) and executes it in the background
			using subprocess.Popen().

			The STDOUT of the new process will be forwarded to STDERR
			to avoid polluting the package list with `--pretend'.
			If one of the called processes is braindead and insists on
			closing one of these descriptors, use `2>&1' to force
			replicating them on shell level.

			This function returns the spawned Popen() instance.
		"""
		try:
			os.chdir(self.getpath())
		except OSError:
			# If the working copy was removed, we'll try to ping
			# the remote server for updates. But for that:
			# 1) user can't use --local-rev,
			# 2) we have to able to get the saved rev.
			# Otherwise, just re-raise the exception.
			if self._opts.local_rev:
				raise
			self.oldrev = self.getsavedrev()
			if not self.oldrev:
				raise
			self.subprocess = None
		else:
			self.oldrev = (not self._opts.local_rev and self.getsavedrev()) or self.getrev()

			if self._opts.network:
				cmd = self.getupdatecmd()
				out.s2(str(self))
				out.s3(cmd)
				self.subprocess = subprocess.Popen(cmd, stdout=sys.stderr, env=self.callenv, shell=True)
			else:
				self.subprocess = None

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
			needs to be rebuilt), this method returns True and calls
			self.diffstat() if appropriate. Otherwise, it returns False.
		"""
		if self.subprocess is None:
			ret = 0
		elif blocking:
			ret = self.subprocess.wait()
		else:
			ret = self.subprocess.poll()
			if ret is None:
				return None

		if ret == 0:
			doingremote = False
			try:
				os.chdir(self.getpath())
			except OSError:
				# The directory could have been removed during update.
				if not self.oldrev:
					raise
				# If we're running offline, just ignore the repo.
				# Otherwise, try to get the current rev off the remote
				# server.
				if not self._opts.network:
					newrev = self.oldrev
				else:
					newrev = self.getremoterev()
					if not newrev:
						raise
					doingremote = True
			else:
				newrev = self.getrev()

			if self._opts.jobs > 1:
				out.s2(str(self))

			if self.revcmp(self.oldrev, newrev):
				out.s3('at rev %s%s%s (no changes)' % (out.green, self.oldrev, out.reset))
				return False
			else:
				if not doingremote and self._opts.diffstat:
					self.diffstat(self.oldrev, newrev)
				out.s3('update from %s%s%s to %s%s%s' % (out.green, self.oldrev, out.reset, out.lime, newrev, out.reset))
				if doingremote:
					raise Exception('remote revision changed, forcing re-fetch')
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

vcs_cache = {}

def GetVCS(eclassname, allowed = []):
	if eclassname not in vcs_cache:
		if allowed and eclassname not in allowed:
			vcs_cache[eclassname] = None
		else:
			try:
				modname = 'SmartLiveRebuild.vcs.%s' % eclassname.replace('-', '_')
				mod = __import__(modname, {}, {}, ['.'], 0)
				for k in dir(mod):
					modvar = getattr(mod, k)
					if issubclass(modvar, VCSSupport) and \
							not issubclass(VCSSupport, modvar):
						vcs_cache[eclassname] = modvar
						break
				else:
					raise ImportError('Unable to find a matching class in %s' % mod)
			except ImportError:
				vcs_cache[eclassname] = None

	return vcs_cache[eclassname]
