# 	vim:fileencoding=utf-8:noet
# (c) 2011-2023 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

import itertools, os, sys, shlex
from copy import copy
from optparse import OptionParser, Option, OptionValueError

from gentoopm import get_package_manager

from . import __version__
from .config import Config, conf_getvcs
from .core import SmartLiveRebuild, SLRFailure
from .output import out


def check_vcslist(opt, optstr, val):
    val = val.split(",")
    for vcs in val:
        if conf_getvcs(vcs) is None:
            raise OptionValueError(
                "option %s: VCS eclass '%s' is not supported." % (optstr, vcs)
            )
    return val


def check_cslist(opt, optstr, val):
    val = val.split(",")
    return val


class SLROption(Option):
    TYPES = Option.TYPES + ("vcslist", "cslist")
    TYPE_CHECKER = copy(Option.TYPE_CHECKER)
    TYPE_CHECKER["vcslist"] = check_vcslist
    TYPE_CHECKER["cslist"] = check_cslist


class CLIConfig(Config):
    def apply_optparse(self, values):
        for k in self.defaults():
            try:
                v = getattr(values, k)
                if v is None:
                    raise ValueError
            except (AttributeError, ValueError):
                pass
            else:
                if isinstance(v, list):
                    v = ",".join(itertools.chain(*v))
                self.set(self._current_section, k, str(v))


def parse_options(argv):
    opt = OptionParser(
        usage="%prog [options] -- [emerge options]",
        version="%%prog %s" % __version__,
        description="Enumerate all live packages in system, check their repositories for updates and remerge the updated ones.",
        option_class=SLROption,
    )
    opt.add_option(
        "-c",
        "--config-file",
        action="store",
        dest="config_file",
        help="Configuration file (default: /etc/portage/smart-live-rebuild.conf)",
    )
    opt.add_option(
        "-C",
        "--no-color",
        action="store_false",
        dest="color",
        help="Disable colorful output.",
    )
    opt.add_option(
        "-d",
        "--debug",
        action="store_true",
        dest="debug",
        help="Die on first failure (useful to debug VCS errors, otherwise missed).",
    )
    opt.add_option(
        "-E",
        "--no-erraneous-merge",
        action="store_false",
        dest="erraneous_merge",
        help="Disable emerging packages for which the update has failed.",
    )
    opt.add_option(
        "-f",
        "--filter-packages",
        action="append",
        type="cslist",
        dest="filter_packages",
        help="Update only named packages (wildcard on package name or cat/pn, prefix with ! for exclusive, can be used multiple times).",
    )
    opt.add_option(
        "-j",
        "--jobs",
        action="store",
        type="int",
        dest="jobs",
        help="Spawn JOBS parallel processes to perform repository updates.",
    )
    opt.add_option(
        "-p",
        "--pretend",
        action="store_true",
        dest="pretend",
        help="Only print a list of the packages which were updated; do not call emerge to rebuild them.",
    )
    opt.add_option(
        "-P",
        "--profile",
        action="store",
        dest="profile",
        help="Configuration profile (config file section) to use (default: smart-live-rebuild)",
    )
    opt.add_option(
        "-q",
        "--quiet",
        action="store_true",
        dest="quiet",
        help="Do not output progress messages, just errors.",
    )
    opt.add_option(
        "-Q",
        "--quickpkg",
        action="store_true",
        dest="quickpkg",
        help="Call quickpkg to create binary backups of packages which are going to be updated.",
    )
    opt.add_option(
        "-r",
        "--remote-only",
        action="store_true",
        dest="remote_only",
        help="Update remote-capable VCSes only (useful with --unprivileged-user).",
    )
    opt.add_option(
        "-S",
        "--no-setuid",
        action="store_false",
        dest="setuid",
        help="Do not switch UID to portage when FEATURES=userpriv is set.",
    )
    opt.add_option(
        "-t",
        "--type",
        action="append",
        type="vcslist",
        dest="type",
        help="Limit rebuild to packages using specific VCS (eclass name). If used multiple times, all specified VCS-es will be used.",
    )
    opt.add_option(
        "-T",
        "--timeout",
        type="int",
        dest="timeout",
        help="Update timeout (0 to disable)",
    )
    opt.add_option(
        "-U",
        "--unprivileged-user",
        action="store_true",
        dest="unprivileged_user",
        help="Allow running as an unprivileged user.",
    )

    return opt.parse_args(argv[1:])


def main(argv):
    pm = get_package_manager()
    pm_conf = pm.config

    # initialize config with defaults
    c = CLIConfig(pm_conf)

    # parse opts to get the config file
    (opts, args) = parse_options(argv)
    c.apply_optparse(opts)

    # do the config file parsing
    c.parse_configfiles()

    # and now reapply the options to override config file defaults
    c.apply_optparse(opts)
    opts = c.get_options()

    if not opts.pretend:
        try:
            import psutil

            def getproc(pid):
                for ps in psutil.get_process_list():
                    if pid == ps.pid:
                        return ps
                raise Exception()

            def getscriptname(ps):
                if os.path.basename(ps.cmdline[0]) != ps.name:
                    return ps.cmdline[0]
                cmdline = ps.cmdline[1:]
                while cmdline[0].startswith("-"):  # omit options
                    cmdline.pop(0)
                return os.path.basename(cmdline[0])

            ps = getproc(os.getppid())
            # traverse upstream to find the emerge process
            while ps.pid > 1:
                if getscriptname(ps) == "emerge":
                    out.s1("Running under the emerge process, assuming --pretend.")
                    opts.pretend = True
                    break
                ps = ps.parent
        except Exception:
            pass

    if os.geteuid() != 0 and opts.unprivileged_user:
        if not opts.pretend:
            out.s1("Running as an unprivileged user, assuming --pretend.")
            opts.pretend = True
        if opts.quickpkg:
            out.err("Running as an unprivileged user, --quickpkg probably won't work")

    try:
        packages = SmartLiveRebuild(opts, pm, cliargs=args)
    except SLRFailure:
        return 1

    if not packages and not any(filter(lambda a: not a.startswith("-"), args)):
        return 0

    if opts.pretend:
        for p in packages:
            print(p)
        return 0
    else:
        cmd = [
            "emerge",
            "--oneshot",
            "--getbinpkg=n",
            "--usepkg-exclude",
            " ".join(packages),
        ]
        cmd.extend(args)
        cmd.extend(packages)
        out.s2(shlex.join(cmd))
        os.execv("/usr/bin/emerge", cmd)
        return 126


def setuptools_main():
    sys.exit(main(sys.argv))
