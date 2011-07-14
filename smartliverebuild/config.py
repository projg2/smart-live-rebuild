#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

import os, sys

try:
	from configparser import ConfigParser, NoOptionError
except ImportError: # py2
	from ConfigParser import ConfigParser, NoOptionError

from smartliverebuild.output import out
from smartliverebuild.vcsload import VCSLoader

conf_getvcs = VCSLoader()

class Config(ConfigParser):
	def __init__(self, pm_conf):
		self._real_defaults = {
			'color': 'True',
			'config_file': '/etc/portage/smart-live-rebuild.conf',
			'debug': 'False',
			'erraneous_merge': 'True',
			'filter_packages': '',
			'jobs': '1',
			'pretend': 'False',
			'profile': 'smart-live-rebuild',
			'quickpkg': 'False',
			'remote_only': 'False',
			'setuid': str(pm_conf.userpriv_enabled),
			'type': '',
			'unprivileged_user': 'False'
		}

		self._current_section = 'DEFAULT'
		ConfigParser.__init__(self, self._real_defaults)

	def apply_dict(self, values):
		for k, v in values.items():
			self.set(self._current_section, k, str(v))

	def parse_configfiles(self):
		cfl = [self.get(self._current_section, 'config_file')]
		sect = self.get(self._current_section, 'profile')

		try:
			while cfl[-1] != '' and self.read(os.path.expanduser(cfl[-1])):
				# config file chaining support
				try:
					cf = self.get(sect, 'config_file')
				except NoOptionError:
					break
				else:
					if cf not in cfl:
						cfl.append(cfl)
					else:
						break
		except Exception as e:
			out.err('Error while parsing configuration file:')
			out.err('%s: %s' % (e.__class__.__name__, e))

		if not self.has_section(sect):
			self.add_section(sect)
		self._current_section = sect

	def get_options(self):
		# values can be accessible both through keys (like a dict)
		# and through attributes (like optparse's values)
		class ConfigValues(object):
			def __getitem__(self, k):
				return getattr(self, k)

			def __setitem__(self, k, v):
				return setattr(self, k, v)

			def __str__(self):
				out = {}
				for k in dir(self):
					if not k.startswith('_'):
						out[k] = getattr(self, k)

				return str(out)

		# use the _real_defaults as type-hint
		val = ConfigValues()

		for k, v in self.items(self._current_section):
			if k not in self._real_defaults:
				val[k] = v
			elif self._real_defaults[k] in ('True', 'False'): # bool
				try:
					val[k] = self.getboolean(self._current_section, k)
				except ValueError:
					out.err('Incorrect boolean value: %s=%s' % (k, v))
					val[k] = (self._real_defaults[k] == 'True')
			elif k == 'jobs': # int
				try:
					val[k] = int(v)
				except ValueError:
					out.err('Incorrect int value: %s=%s' % (k, v))
					val[k] = int(self._real_defaults[k])
			elif k == 'filter_packages': # list
				if v != '':
					val[k] = v.split(',')
				else:
					val[k] = None
			elif k == 'type':
				if v != '':
					val[k] = []
					for vcs in v.split(','):
						if conf_getvcs(vcs):
							val[k].append(vcs)
						else:
							out.err('VCS type not supported: %s' % vcs)

					if not val[k]:
						out.err('None of specified VCS types matched, aborting.')
						sys.exit(1)
				else:
					val[k] = None
			else:
				val[k] = v

		return val
