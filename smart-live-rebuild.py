#!/usr/bin/python
# Check all live ebuilds for updates and rebuild them if necessary.
# (C) 2010 Michał Górny <gentoo@mgorny.alt.pl>
# Released under the terms of the 3-clause BSD license

import bz2, codecs, re, os, sys, subprocess
import portage

root = portage.settings['ROOT']
db = portage.db[root]["vartree"].dbapi

utfdec = codecs.getdecoder('utf8')
declre = re.compile('^declare -[-x] ([A-Z_]+)="(.*)"$')

rebuilds = {}

class out:
	@classmethod
	def s1(self, msg):
		self.out('*** %s\n' % msg)
	@classmethod
	def s2(self, msg):
		self.out('->  %s\n' % msg)
	@classmethod
	def s3(self, msg):
		self.out('--> %s\n' % msg)

	@staticmethod
	def out(msg):
		sys.stderr.write(msg)

class VCSSupport:
	inherit = None
	reqenv = []

	@classmethod
	def match(self, inherits):
		if self.inherit is None:
			raise NotImplementedError('VCS class needs to either override inherit or match()')
		return (self.inherit in inherits)

	def __init__(self, cpv, env):
		self.cpv = [cpv]
		self.reqenv = list(self.reqenv) # clone it
		self.env = {}
		if len(self.reqenv) >= 1:
			for l in env:
				m = declre.match(l)
				if m is not None and m.group(1) in self.reqenv:
					self.env[m.group(1)] = m.group(2)
					self.reqenv.remove(m.group(1))
					if len(self.reqenv) < 1:
						break
			else:
				raise KeyError('Environment does not declare: %s' % self.reqenv)
		if self.env['EGIT_HAS_SUBMODULES'] == 'true':
			raise NotImplementedError('Submodules are not supported')

	def append(self, vcs):
		if not isinstance(vcs, self.__class__):
			raise ValueError('Unable to append %s to %s' % (vcs.__class__, self.__class__))
		self.cpv.append(vcs.cpv[0])

	@staticmethod
	def call(cmd):
		return subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0].split('\n')[0]

class GitSupport(VCSSupport):
	inherit = 'git'
	reqenv = ['EGIT_STORE_DIR', 'EGIT_PROJECT', 'EGIT_UPDATE_CMD', 'EGIT_OPTIONS', 'EGIT_BRANCH', 'EGIT_HAS_SUBMODULES', 'EGIT_REPO_URI']

	def getpath(self):
		return u'%s/%s' % (self.env['EGIT_STORE_DIR'], self.env['EGIT_PROJECT'])

	def update(self):
		out.s2(self.env['EGIT_REPO_URI'])
		os.chdir(self.getpath())
		oldrev = self.call(['git', 'rev-parse', self.env['EGIT_BRANCH']])
		cmd = '%s %s origin %s:%s' % (self.env['EGIT_UPDATE_CMD'], self.env['EGIT_OPTIONS'], self.env['EGIT_BRANCH'], self.env['EGIT_BRANCH'])
		out.s3(cmd)
		subprocess.Popen(cmd, shell=True).wait()
		newrev = self.call(['git', 'rev-parse', self.env['EGIT_BRANCH']])
		if oldrev == newrev:
			out.s3('at rev %s (not updated)' % oldrev)
			return False
		else:
			out.s3('update from %s to %s' % (oldrev, newrev))
			return True

vcsl = [GitSupport]

out.s1('Enumerating packages ...')

for cpv in db.cpv_all():
	def getenv():
		fn = u'%s/environment.bz2' % db.getpath(cpv)
		f = bz2.BZ2File(fn, 'r')
		return utfdec(f.read())[0].split('\n')

	inherits = db.aux_get(cpv, ['INHERITED'])[0].split()

	for vcs in vcsl:
		if vcs.match(inherits):
			env = getenv()
			vcs = vcs(cpv, env)
			dir = vcs.getpath()
			if dir not in rebuilds:
				rebuilds[dir] = vcs
			else:
				rebuilds[dir].append(vcs)

out.s1('Updating repositories ...')
packages = []

for (dir, vcs) in rebuilds.items():
	if vcs.update():
		packages.extend(vcs.cpv)

if len(packages) < 1:
	out.s1('No updates found')
else:
	out.s1('Calling emerge to rebuild %d packages ...' % len(packages))
	cmd = ['emerge', '--oneshot']
	cmd.extend(sys.argv[1:])
	cmd.extend(['=%s' % x for x in packages])
	out.s2(' '.join(cmd))
	os.execv('/usr/bin/emerge', cmd)
