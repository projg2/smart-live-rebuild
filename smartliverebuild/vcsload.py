#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

class VCSLoader(object):
	vcs_cache = {}

	def __call__(self, eclassname, allowed = []):
		if eclassname not in self.vcs_cache:
			if allowed and eclassname not in allowed:
				self.vcs_cache[eclassname] = None
			else:
				modname = 'smartliverebuild.vcs.%s' % eclassname.replace('-', '_')
				try:
					mod = __import__(modname, {}, {}, ['.'], 0)
				except ImportError:
					self.vcs_cache[eclassname] = None
				else:
					for k in dir(mod):
						if k.endswith('Support') and \
								k[:-7].lower() == eclassname.replace('-', ''):
							self.vcs_cache[eclassname] = getattr(mod, k)
							break
					else:
						raise ImportError('Unable to find a matching class in %s' % modname)

		return self.vcs_cache[eclassname]

GetVCS = VCSLoader()
