"""Command line interface of Acacia."""

__all__ = ["build_argparser", "get_config", "run", "main"]

import argparse
import os
import shutil
import sys

from acaciamc.compiler import Compiler, Config
from acaciamc.error import Error as CompileError
from acaciamc.localization import localize
from acaciamc.tokenizer import is_idstart, is_idcontinue

_NOTGIVEN = object()


def fatal(message: str):
    print(localize("cli.fatal") % message, file=sys.stderr)
    sys.exit(1)


def build_argparser():
    argparser = argparse.ArgumentParser(
        prog='acacia', description=localize("cli.description"),
    )
    argparser.add_argument(
        'file',
        help=localize("cli.argshelp.file")
    )
    argparser.add_argument(
        '-o', '--out', metavar='PATH',
        help=localize("cli.argshelp.out")
    )
    argparser.add_argument(
        "-v", "--mc-version", metavar="VERSION",
        help=localize("cli.argshelp.mcversion")
    )
    argparser.add_argument(
        '-e', '--education-edition',
        action='store_true',
        help=localize("cli.argshelp.educationedition")
    )
    argparser.add_argument(
        '-s', '--scoreboard', metavar='OBJECTIVE',
        help=localize("cli.argshelp.scoreboard")
    )
    argparser.add_argument(
        '-f', '--function-folder', metavar='PATH',
        help=localize("cli.argshelp.functionfolder")
    )
    argparser.add_argument(
        '-m', '--main-file', metavar='NAME',
        help=localize("cli.argshelp.mainfile")
    )
    argparser.add_argument(
        '-t', '--entity-tag', metavar="TAG",
        help=localize("cli.argshelp.entitytag")
    )
    argparser.add_argument(
        '-d', '--debug-comments',
        action='store_true',
        help=localize("cli.argshelp.debugcomments")
    )
    argparser.add_argument(
        "-O", "--no-optimize",
        action='store_true',
        help=localize("cli.argshelp.nooptimize")
    )
    argparser.add_argument(
        '-u', '--override-old',
        action='store_true',
        help=localize("cli.argshelp.overrideold")
    )
    argparser.add_argument(
        '-i', '--init-file', nargs='?', metavar='NAME', const=_NOTGIVEN,
        help=localize("cli.argshelp.initfile")
    )
    argparser.add_argument(
        '--internal-folder', metavar="NAME",
        help=localize("cli.argshelp.internalfolder")
    )
    argparser.add_argument(
        '--encoding', metavar="CODEC", default="utf-8",
        help=localize("cli.argshelp.encoding")
    )
    argparser.add_argument(
        '--verbose',
        action='store_true',
        help=localize("cli.argshelp.verbose")
    )
    argparser.add_argument(
        '--max-inline-file-size', metavar="SIZE", type=int,
        help=localize("cli.argshelp.maxinline")
    )
    return argparser


def check_id(name: str):
    """Raise ValueError if `name` is not a valid Acacia identifier."""
    if not name:
        raise ValueError(localize("cli.checkid.empty"))
    if not is_idstart(name[0]):
        raise ValueError(localize("cli.checkid.idstart") % name[0])
    for c in name:
        if not is_idcontinue(c):
            raise ValueError(localize("cli.checkid.idcontinue") % c)


def assert_id(name: str, option: str):
    """Make sure `name` is a valid Acacia identifier."""
    try:
        check_id(name)
    except ValueError as e:
        fatal(localize("cli.assertid.fatal")
              .format(option=option, msg=e.args[0]))


def get_config(args) -> Config:
    """Create a `Config` object from `args`."""
    kwds = {
        'debug_comments': bool(args.debug_comments),
        'education_edition': bool(args.education_edition),
        'optimizer': not bool(args.no_optimize),
        'encoding': args.encoding
    }
    if args.scoreboard:
        assert_id(args.scoreboard, '--scoreboard')
        kwds["scoreboard"] = args.scoreboard
    if args.function_folder:
        path = [p for p in args.function_folder.split("/") if p]
        for p in path:
            try:
                check_id(p)
            except ValueError as e:
                fatal(localize("cli.getconfig.invalidfunctionfolder")
                      .format(msg=e.args[0], name=p))
        kwds["root_folder"] = '/'.join(path)
    if args.main_file:
        assert_id(args.main_file, '--main-file')
        kwds["main_file"] = args.main_file
    if args.entity_tag:
        kwds["entity_tag"] = args.entity_tag
    if args.mc_version:
        numlist = args.mc_version.split(".")
        try:
            t = tuple(map(int, numlist))
            if len(t) <= 1:
                raise ValueError
            if any(v < 0 for v in t):
                raise ValueError
        except ValueError:
            fatal(localize("cli.getconfig.invalidmcversion") % args.mc_version)
        if t < (1, 19, 50):
            fatal(localize("cli.getconfig.mcversiontooold") % args.mc_version)
        kwds["mc_version"] = t
    if args.max_inline_file_size is not None:
        if args.max_inline_file_size < 0:
            fatal(localize("cli.getconfig.maxinlinetoolow")
                  % args.max_inline_file_size)
        kwds["max_inline_file_size"] = args.max_inline_file_size
    if args.init_file:
        kwds["split_init"] = True
        if args.init_file is not _NOTGIVEN:
            assert_id(args.init_file, '--init-file')
            kwds["init_file"] = args.init_file
    if args.internal_folder:
        assert_id(args.internal_folder, '--internal-folder')
        kwds["internal_folder"] = args.internal_folder
    return Config(**kwds)


def try_rmtree(path: str):
    """
    Delete `path` if this path exists.
    Report any error as `fatal`.
    """
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
        except OSError as e:
            fatal(localize("cli.tryrmtree.failure")
                  .format(path=path, message=e.strerror))


def run(args):
    if not os.path.exists(args.file):
        fatal('file not found: %s' % args.file)
    if not os.path.isfile(args.file):
        fatal('not a file: %s' % args.file)

    if args.out:
        out_path = os.path.realpath(args.out)
    else:  # default out path: ./<name of source>.acaout
        out_path, _ = os.path.splitext(args.file)
        out_path = os.path.realpath(out_path) + '.acaout'

    cfg = get_config(args)

    if not os.path.exists(out_path):
        out_up = os.path.dirname(out_path)
        if not os.path.exists(out_up):
            fatal(localize("cli.run.outputnotfound") % out_up)
        os.mkdir(out_path)

    try:
        compiler = Compiler(args.file, cfg)
        if args.override_old:
            # Remove old output directory if -u is set and compilation
            # succeeded.
            try_rmtree(os.path.join(out_path, cfg.root_folder))
        compiler.output(out_path)
    except CompileError as err:
        fatal(err.full_msg())
    except Exception as err:
        import traceback
        if args.verbose:
            traceback.print_exc()
            print(file=sys.stderr)
            fatal(localize("cli.run.aboveunexpectederror"))
        else:
            fatal(
                localize("cli.run.unexpectederror")
                % traceback.format_exception_only(err)[-1].strip()
            )


def main():
    argparser = build_argparser()
    args = argparser.parse_args()
    run(args)
