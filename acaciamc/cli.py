"""Command line interface of Acacia."""

__all__ = ["build_argparser", "apply_config", "run", "main"]

import argparse
import os
import shutil
import sys

from acaciamc.constants import Config
from acaciamc.error import Error as CompileError
from acaciamc.compiler import Compiler

DESCRIPTION = (
    'Compiler of Acacia, a programming language that runs in Minecraft '
    'Bedrock Edition by compiling code into mcfunction files.'
)
_NOTGIVEN = object()

def fatal(message: str):
    print("acacia: error: %s" % message, file=sys.stderr)
    sys.exit(1)

def build_argparser():
    argparser = argparse.ArgumentParser(
        prog='acacia', description=DESCRIPTION,
    )
    argparser.add_argument(
        'file',
        help='the file to compile'
    )
    argparser.add_argument(
        '-o', '--out', metavar='PATH',
        help='output directory'
    )
    argparser.add_argument(
        "-v", "--mc-version", metavar="VERSION",
        help="Minecraft version (e.g. 1.19.50)"
    )
    argparser.add_argument(
        '-s', '--scoreboard', metavar='OBJECTIVE',
        help='the scoreboard that Acacia uses to store data (default "acacia")'
    )
    argparser.add_argument(
        '-f', '--function-folder', metavar='PATH',
        help='path relative to "functions" directory in a behavior pack where'
             ' Acacia generates its output .mcfunction files (default "", i.e.'
             ' generate directly at "functions" level)'
    )
    argparser.add_argument(
        '-m', '--main-file', metavar='NAME',
        help='name of the mcfunction file that executes your program '
             '(default "main")'
    )
    argparser.add_argument(
        '-n', '--entity-name', metavar="NAME",
        help='entity name prefix'
    )
    argparser.add_argument(
        '-t', '--entity-tag', metavar="TAG",
        help='entity tag prefix'
    )
    argparser.add_argument(
        '-d', '--debug-comments',
        action='store_true',
        help='add debugging comments to output files'
    )
    argparser.add_argument(
        "-O", "--no-optimize",
        action='store_true',
        help="disable optimization"
    )
    argparser.add_argument(
        '-u', '--override-old',
        action='store_true',
        help='remove the old output contents (EVERYTHING IN DIRECTORY!)'
    )
    argparser.add_argument(
        '-i', '--init-file', nargs='?', metavar='NAME', const=_NOTGIVEN,
        help='if set, split initialization commands from main mcfunction '
             'file into given file (default "init")'
    )
    argparser.add_argument(
        '--internal-folder', metavar="NAME",
        help='name of the folder where Acacia stores its internal files'
    )
    argparser.add_argument(
        '--encoding', metavar="CODEC", default="utf-8",
        help='encoding of file (default "utf-8")'
    )
    argparser.add_argument(
        '--verbose',
        action='store_true',
        help='show full traceback message when encountering unexpected errors'
    )
    argparser.add_argument(
        '--max-inline-file-size', metavar="SIZE", type=int,
        help='optimizer option: maximum size for a function that is called '
             'with /execute conditions to be inlined (default 20)'
    )
    return argparser

def check_id(name: str):
    """Raise ValueError if `name` is not a valid Acacia identifier."""
    if not name:
        raise ValueError('can\'t be empty')
    if name[0].isdecimal():
        raise ValueError('can\'t start with a number')
    for s in name:
        if not (s.isalnum() or s == '_'):
            raise ValueError('invalid character %r' % s)

def assert_id(name: str, option: str):
    """Make sure `name` is a valid Acacia identifier."""
    try:
        check_id(name)
    except ValueError as e:
        fatal('option %s: %s' % (option, e.args[0]))

def apply_config(args):
    """Apply arguments to `Config`."""
    if args.debug_comments:
        Config.debug_comments = True
    if args.scoreboard:
        assert_id(args.scoreboard, '--scoreboard')
        Config.scoreboard = args.scoreboard
    if args.function_folder:
        path = [p for p in args.function_folder.split("/") if p]
        for p in path:
            try:
                check_id(p)
            except ValueError as e:
                fatal('option --function-folder: invalid name %r: %s'
                      % (p, e.args[0]))
        Config.root_folder = args.function_folder
    if args.main_file:
        assert_id(args.main_file, '--main-file')
        Config.main_file = args.main_file
    if args.entity_name:
        Config.entity_name = args.entity_name
    if args.entity_tag:
        Config.entity_tag = args.entity_tag
    if args.mc_version:
        numlist = args.mc_version.split(".")
        try:
            Config.mc_version = tuple(map(int, numlist))
            if len(Config.mc_version) <= 1:
                raise ValueError
            if any(v < 0 for v in Config.mc_version):
                raise ValueError
        except ValueError:
            fatal('invalid Minecraft version: %s' % args.mc_version)
    if args.no_optimize:
        Config.optimizer = False
    if args.max_inline_file_size is not None:
        if args.max_inline_file_size < 0:
            fatal('max inline file size must >= 0: %s'
                  % args.max_inline_file_size)
        Config.max_inline_file_size = args.max_inline_file_size
    if args.init_file:
        Config.split_init = True
        if args.init_file is not _NOTGIVEN:
            assert_id(args.init_file, '--init-file')
            Config.init_file = args.init_file
    if args.internal_folder:
        assert_id(args.internal_folder, '--internal-folder')
        Config.internal_folder = args.internal_folder

def run(args):
    if not os.path.exists(args.file):
        fatal('file not found: %s' % args.file)
    if not os.path.isfile(args.file):
        fatal('not a file: %s' % args.file)

    encoding = args.encoding

    if args.out:
        out_path = os.path.realpath(args.out)
    else:  # default out path: ./<name of source>.acaout
        out_path, _ = os.path.splitext(args.file)
        out_path = os.path.realpath(out_path)
        out_path += '.acaout'

    if args.override_old:
        # remove old output directory
        rm_path = os.path.join(out_path, Config.root_folder)
        if os.path.exists(rm_path):
            shutil.rmtree(rm_path)

    if not os.path.exists(out_path):
        os.mkdir(out_path)

    apply_config(args)

    try:
        compiler = Compiler(args.file, open_args={'encoding': encoding})
        compiler.output(out_path)
    except CompileError as err:
        fatal(err.full_msg())
    except Exception as err:
        import traceback
        if args.verbose:
            traceback.print_exc()
            print()
            fatal("the above unexpected error occurred when compiling")
        else:
            fatal(
                'unexpected error when compiling: %s'
                % traceback.format_exception_only(err)[-1].strip()
            )

def main():
    argparser = build_argparser()
    args = argparser.parse_args()
    run(args)
