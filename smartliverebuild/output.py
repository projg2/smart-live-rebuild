#	vim:fileencoding=utf-8
# (c) 2010 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

import sys

class SLROutput(object):
	red = '\033[1;31m'
	green = '\033[32m'
	lime = '\033[1;32m'
	yellow = '\033[1;33m'
	cyan = '\033[36m'
	turq = '\033[1;36m'
	white = '\033[1;37m'
	reset = '\033[0m'

	s1reset = lime
	s2reset = green
	s3reset = cyan
	errreset = yellow

	def __init__(self):
		self._cur_header = None

	def monochromize(self):
		for k in dir(self):
			if not k.startswith('_'):
				v = getattr(self, k)
				if isinstance(v, str) and v.startswith('\033'):
					setattr(self, k, '')

	def silence(self):
		self.s1 = lambda x: None
		self.s2 = lambda x: None
		self.s3 = lambda x: None

	def s1(self, msg):
		self.out('%s*** %s%s\n' % (self.s1reset, msg, self.reset))
		self._cur_header = None
	def s2(self, msg):
		self.out('%s->%s  %s\n' % (self.s2reset, self.reset, msg))
	def s3(self, msg):
		self.out('%s-->%s %s\n' % (self.s3reset, self.reset, msg))

	def pkgs(self, header, msg):
		if self._cur_header != header:
			self.s2(header)
			self._cur_header = header
		self.s3(msg)

	def err(self, msg):
		self.out('%s!!!%s %s%s%s\n' % (self.red, self.reset, self.errreset, msg, self.reset))
		self._cur_header = None

	def out(self, msg):
		sys.stderr.write(msg)

out = SLROutput()
