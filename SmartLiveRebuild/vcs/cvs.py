#	vim:fileencoding=utf-8
# (c) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license or the GPL-2 license.

import hashlib, tempfile

from SmartLiveRebuild.vcs import VCSSupport

class CVSSupport(VCSSupport):
	reqenv = ['ECVS_AUTH', 'ECVS_CVS_COMMAND', 'ECVS_MODULE', 'ECVS_SERVER', 'ECVS_TOP_DIR', 'ECVS_USER']
	optenv = ['ECVS_BRANCH', 'ECVS_CLEAN', 'ECVS_LOCAL', 'ECVS_LOCALNAME', 'ECVS_PASS',
			'ECVS_RUNAS', 'ECVS_UP_OPTS', 'ECVS_VERSION']

	def __init__(self, *args):
		VCSSupport.__init__(self, *args)
		if self.env['ECVS_RUNAS']:
			raise NotImplementedError('ECVS_RUNAS is not implemented (yet).')
		elif self.env['ECVS_AUTH'] != 'pserver':
			raise NotImplementedError('ECVS_AUTH=%s while only pserver is supported.' % self.env['ECVS_AUTH'])

	def getpath(self):
		return '%s/%s' % (self.env['ECVS_TOP_DIR'], self.env['ECVS_LOCALNAME'] or self.env['ECVS_MODULE'])

	def __str__(self):
		return '%s (%s)' % (self.env['ECVS_SERVER'], self.env['ECVS_MODULE']) or VCSSupport.__str__(self)

	def getsavedrev(self):
		return self.env['ECVS_VERSION']

	def getrev(self):
		inp = self.call(['find', self.getpath()] + '-ipath */CVS/Entries -exec cat {} +'.split()).split('\n')
		del inp[-1] # drop the trailing newline for sorting
		inp.sort()
		inp.append('') # and readd it
		hasher = hashlib.sha1()
		hasher.update('\n'.join(inp))

		return hasher.hexdigest()

	def getupdatecmd(self):
		opts = []
		if self.env['ECVS_LOCAL']:
			opts.append('-l')
		if self.env['ECVS_BRANCH']:
			opts.append('-r%s' % self.env['ECVS_BRANCH'])
		if self.env['ECVS_CLEAN']:
			opts.append('-C')

		# XXX: server switching?

		login_root = ':%s:%s:%s@%s' % (self.env['ECVS_AUTH'], self.env['ECVS_USER'],
				self.env['ECVS_PASS'], self.env['ECVS_SERVER'])
		login_cmd = '%s -f -d "%s" login' % (self.env['ECVS_CVS_COMMAND'], login_root)
		up_root = ':%s:%s@%s' % (self.env['ECVS_AUTH'], self.env['ECVS_USER'],
				self.env['ECVS_SERVER'])
		up_cmd = '%s -f -d "%s" update %s %s' % (self.env['ECVS_CVS_COMMAND'], up_root,
				self.env['ECVS_UP_OPTS'], ' '.join(opts))

		# CVS is stupid as hell and tries to close STDOUT, which is
		# redirected... making long story short, we need to do some
		# random magic to make things work with our Popen()...
		stdout_cmd = 'exec 2>&1'

		cvs_passfile = tempfile.NamedTemporaryFile(delete=False)
		env_cmd = 'export CVS_PASSFILE="%s" HOME=' % cvs_passfile.name
		trap_cmd = 'trap \'rm -f "%s"\' EXIT' % cvs_passfile.name

		cmd = '; '.join([trap_cmd, env_cmd, stdout_cmd, login_cmd, up_cmd])

		return cmd

myvcs = CVSSupport
