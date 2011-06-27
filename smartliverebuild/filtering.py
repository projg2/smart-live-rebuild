#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

import fnmatch, re

from portage.versions import catpkgsplit

wildcard_re = re.compile(r'^(!)?(?:([A-Za-z0-9+_.?*\[\]-]+)/)?([A-Za-z0-9+_?*\[\]-]+)$')
class PackageFilter(object):
	"""
	Package filtering framework.
	
	>>> pf = PackageFilter(['--pretend', '!*', 'app-foo/f*', 'smart-live-rebuild', '-avD'])
	>>> [f for f in pf.nonmatched] # bang always matches
	['--pretend', 'app-foo/f*', 'smart-live-rebuild', '-avD']
	>>> pf('app-foo/foo-123')
	True
	>>> pf('app-foo/bar-123')
	False
	>>> pf('app-bar/foo-321')
	False
	>>> pf('app-portage/smart-live-rebuild-9999')
	True
	>>> [f for f in pf.nonmatched]
	['--pretend', '-avD']
	"""

	class PackageMatcher(object):
		""" A single package filter. """

		def __init__(self, wildcard):
			""" Init filter for pattern. """
			m = wildcard_re.match(wildcard)
			self.broken = not m

			def makere(s):
				return re.compile(r'^%s$' % fnmatch.translate(s))

			if not self.broken:
				self.exclusive = bool(m.group(1))
				if m.group(2):
					self.category = makere(m.group(2))
				else:
					self.category = re.compile('.')
				self.pn = makere(m.group(3))
#			XXX: the below test catches cliargs as well
#			else:
#				sys.stderr.write('Incorrect filter string: %s\n' % wildcard)

			# .matched is used only on inclusive args
			self.matched = self.exclusive
			self.wildcard = wildcard

		def __call__(self, cpv):
			cat, pkg, ver, rev = catpkgsplit(cpv)
			m = bool(self.category.match(cat) and self.pn.match(pkg))
			self.matched |= m
			return m ^ self.exclusive

	def __init__(self, wlist):
		""" Init filters from pattern list. """
		if wlist:
			pmatchers = [self.PackageMatcher(w) for w in wlist]
			self._broken = filter(lambda f: f.broken, pmatchers)
			self._pmatchers = filter(lambda f: not f.broken, pmatchers)
			for f in self._pmatchers:
				self._default_pass = f.exclusive
				break
		else:
			self._pmatchers = ()
			self._default_pass = True

	def __call__(self, cpv):
		""" Execute filtering on CPV. """
		r = self._default_pass
		for m in self._pmatchers:
			if m.exclusive:
				r &= m(cpv)
			else:
				r |= m(cpv)
		return r

	@property
	def nonmatched(self):
		""" Iterate over non-matched args. """

		for m in self._pmatchers:
			if not m.matched:
				yield m.wildcard
		for m in self._broken:
			yield m.wildcard
