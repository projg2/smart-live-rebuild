#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

from smartliverebuild.vcs import RemoteVCSSupport

class VCSLoader(object):
	vcs_cache = {}

	def __call__(self, eclassname, allowed = [], remote_only = False):
		if eclassname not in self.vcs_cache:
			self.vcs_cache[eclassname] = None
			if not allowed or eclassname in allowed:
				modname = 'smartliverebuild.vcs.%s' % eclassname.replace('-', '_')
				try:
					mod = __import__(modname, {}, {}, ['.'], 0)
				except ImportError:
					pass
				else:
					for k in dir(mod):
						if k.endswith('Support') and \
								k[:-7].lower() == eclassname.replace('-', ''):
							vcscl = getattr(mod, k)
							if remote_only and not issubclass(vcscl, RemoteVCSSupport):
								break
							self.vcs_cache[eclassname] = vcscl
							break
					else:
						raise ImportError('Unable to find a matching class in %s' % modname)

		return self.vcs_cache[eclassname]

GetVCS = VCSLoader()
