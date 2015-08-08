#	vim:fileencoding=utf-8:noet
# (c) 2015 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

import os
import subprocess
import sys
import tempfile

from . import BaseVCSSupport, OtherEclass
from ..output import out

custom_functions = ''.join('''
debug-print-function() {
	:;
};

elog() {
	einfo "${@}";
};

die() {
	eerror "${@}";
	exit 2;
};

:
'''.splitlines())

class NeedRebuildPhaseSupport(BaseVCSSupport):
	reqenv = []

	def __init__(self, *args, **kwargs):
		if kwargs['environ']('declare -f pkg_needrebuild') != 0:
			raise OtherEclass()

		self._pkg = kwargs['pkg']
		return BaseVCSSupport.__init__(self, *args, **kwargs)

	def __str__(self):
		return self._cpv

	@property
	def updatecmd(self):
		return ': pkg_needrebuild'

	@property
	def savedrev(self):
		pass

	def call_phase(self, pkg):
		stderr_f = tempfile.NamedTemporaryFile()
		# TODO: prefix support
		ret = pkg.environ('%s; . %s; pkg_needrebuild &>%s' % (custom_functions, repr('/lib/gentoo/functions.sh'), repr(stderr_f.name)))
		if ret == 0:
			os.write(1, b'yes')
		elif ret == 1:
			os.write(1, b'no')
		else:
			os.write(1, b'error')

		stderr_f.seek(0)
		os.write(2, stderr_f.read())

	def _startupdate(self):
		BaseVCSSupport._startupdate(self,
				popenargs = {
					'stdout': subprocess.PIPE,
					'stderr': subprocess.PIPE,
					'preexec_fn': lambda: self.call_phase(self._pkg),
				})

	def parseoutput(self, output):
		return output

	def _finishupdate(self, output):
		if output == 'error':
			raise Exception('pkg_needrebuild() errored out')
		elif output == 'yes':
			out.pkgs(self._header, '%schanges found, rebuild needed%s'
					% (out.lime, out.reset))
			return True
		elif output == 'no':
			out.pkgs(self._header, '%sno changes found%s'
					% (out.green, out.reset))
			return False
		else:
			raise Exception('Invalid output from pkg_needrebuild() runner: %s' % output)
