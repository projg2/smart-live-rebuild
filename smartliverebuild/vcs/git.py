#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

from smartliverebuild.vcs.git_2 import Git2Support

class GitSupport(Git2Support):
	def __init__(self, *args, **kwargs):
		Git2Support.__init__(self, *args, **kwargs)
		if len(self.repo_uris) != 1:
			raise ValueError('EGIT_REPO_URI has to contain a single URI (not "%s")' \
					% self.env['EGIT_REPO_URI'])
