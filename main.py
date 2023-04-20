# Main file of Acacia Compiler
from acaciamc.constants import Config
from acaciamc.error import Error as CompileError
from acaciamc.compiler import Compiler

import argparse
import os
import shutil

desc = '''
Compiler of Acacia, a language that dedicates
to simplize the command system of Minecraft
'''

def error(msg):
    print('acacia: error: ' + msg)
    exit(2)

# --- SET ARGPARSER ---

argparser = argparse.ArgumentParser(
    prog = 'acacia',
    description = desc,
)

argparser.add_argument(
    'file',
    help = 'the file to compile'
)

argparser.add_argument(
    '-o', '--out',
    metavar = 'PATH',
    help = 'output directory'
)

argparser.add_argument(
    '-s', '--scoreboard',
    metavar = 'OBJECTIVE',
    help = 'the scoreboard that Acacia uses to store data (default "acacia")'
)

argparser.add_argument(
    '-f', '--function-folder',
    metavar = 'NAME',
    help = 'the subfolder of `functions` in data pack that Acacia uses to '
        'store output .mcfunction files'
)

argparser.add_argument(
    '-i', '--indent',
    type = int,
    metavar = 'NUM',
    help = 'count of spaces that an indented block should have'
)

argparser.add_argument(
    '-d', '--debug-comments',
    action = 'store_true',
    help = 'add debugging comments to output files'
)

argparser.add_argument(
    '--override-old',
    action = 'store_true',
    help = 'remove the old output contents (EVERYTHING IN DIRECTORY!)'
)

argparser.add_argument(
    '--encoding',
    help = 'encoding of file (default "utf-8")'
)

argparser.add_argument(
    '--verbose',
    action = 'store_true',
    help = 'show full traceback message when encountering unexpected errors'
)

args = argparser.parse_args()

# --- ARGUMENT HANDLE ---
def check_id(name: str, option: str):
    # check if name is a valid Acacia identifier
    if not name:
        error('option "%s" can\'t be empty' % option)
    if name[0].isdecimal():
        error('option "%s" can\'t start with a number' % option)
    for s in name:
        if not (s.isalnum() or s == '_'):
            error('invalid character "%s" for option "%s"' % (s, option))

# make sure that the file is available
if not os.path.exists(args.file):
    error('file not found: %s' % args.file)
if not os.path.isfile(args.file):
    error('not a file: %s' % args.file)

# --- Config ARGS ---

if args.indent:
    if args.indent <= 0:
        error('indent number must be positive')
    Config.indent = args.indent
if args.debug_comments:
    Config.debug_comments = True
if args.scoreboard:
    check_id(args.scoreboard, 'scoreboard')
    Config.scoreboard = args.scoreboard
if args.function_folder:
    check_id(args.function_folder, 'function folder')
    Config.function_folder = args.function_folder
if args.encoding is not None:
    encoding = args.encoding
else:
    encoding = 'utf-8'

# --- PATH RELATED ARGS ---

if args.out:
    out_path = os.path.realpath(args.out)
else: # default out path: ./<name of source>.acaout
    out_path, _ = os.path.splitext(args.file)
    out_path = os.path.realpath(out_path)
    out_path += '.acaout'

if args.override_old:
    # remove old output directory
    rm_path = os.path.join(out_path, Config.function_folder)
    if os.path.exists(rm_path):
        shutil.rmtree(rm_path)

if not os.path.exists(out_path):
    os.mkdir(out_path)

# --- START COMPILE ---

try:
    Compiler(args.file, open_args = {
        'encoding': encoding
    }).output(out_path)
except CompileError as err:
    error(str(err))
except Exception as err:
    if args.verbose:
        raise
    else:
        error('unexpected error when compiling: %s' % err)
