#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

"""
>>> wildcard_re.match('--pretend')
>>> wildcard_re.match('-avD')
>>> wildcard_re.match('a-package') # doctest: +ELLIPSIS
<...>
>>> wildcard_re.match('-not-a-package')
>>> wildcard_re.match('another/-broken')
>>> wildcard_re.match('but-this/one-s-fine++') # doctest: +ELLIPSIS
<...>
>>> wildcard_re.match('[a-z]pp-*/*bar??') # doctest: +ELLIPSIS
<...>
>>> wildcard_re.match('a/b') # doctest: +ELLIPSIS
<...>
>>> wildcard_re.match('a') # doctest: +ELLIPSIS
<...>
"""

import fnmatch, re

wildcard_re = re.compile(r'^(!)?(?:([A-Za-z0-9_?*\[\]][A-Za-z0-9+_.?*\[\]-]*)/)?([A-Za-z0-9_?*\[\]][A-Za-z0-9+_?*\[\]-]*)$')

class PackageFilter(object):
	"""
	Package filtering framework.

	>>> pf = PackageFilter(['--pretend', '!*', 'app-foo/f*', 'smart-live-rebuild', '-avD'])
	>>> [f for f in pf.nonmatched] # bang always matches
	['--pretend', 'app-foo/f*', 'smart-live-rebuild', '-avD']
	>>> pf('app-foo/foo')
	True
	>>> pf('app-foo/bar')
	False
	>>> pf('app-bar/foo')
	False
	>>> pf('app-portage/smart-live-rebuild')
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
				self.regexp = re.compile(r'^%s$' % fnmatch.translate(
					'%s/%s' % (m.group(2) or '*', m.group(3))))
				# .matched is used only on inclusive args
				self.matched = self.exclusive

#			XXX: the below test catches cliargs as well
#			else:
#				sys.stderr.write('Incorrect filter string: %s\n' % wildcard)

			self.wildcard = wildcard

		def __call__(self, cp):
			m = bool(self.regexp.match(cp))
			self.matched |= m
			return m ^ self.exclusive

	def __init__(self, wlist):
		""" Init filters from pattern list. """
		if wlist:
			self._pmatchers = [self.PackageMatcher(w) for w in wlist]
			for f in self._pmatchers:
				if not f.broken:
					self._default_pass = f.exclusive
					return
		else:
			self._pmatchers = ()
		self._default_pass = True

	def __call__(self, pkg):
		""" Execute filtering on a package. """
		cp = pkg.key
		r = self._default_pass
		for m in self._pmatchers:
			if m.broken:
				pass
			elif m.exclusive:
				r &= m(cp)
			else:
				r |= m(cp)
		return r

	@property
	def nonmatched(self):
		""" Iterate over non-matched args. """

		for m in self._pmatchers:
			if m.broken or not m.matched:
				yield m.wildcard
