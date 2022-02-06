# 	vim:fileencoding=utf-8:noet
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

from .git_r3 import GitR3Support


class Git2Support(GitR3Support):
    def __init__(self, *args, **kwargs):
        kwargs["want_r2"] = True
        GitR3Support.__init__(self, *args, **kwargs)
