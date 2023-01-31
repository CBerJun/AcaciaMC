# Export useful things
from .base import *
from .types import * # import these first!
from .callable import *
from .module import *
from .boolean import *
from .integer import *
from .string import *
from .none import *

BUILTIN_CALLRESULTS = {
    BuiltinIntType: IntCallResult,
    BuiltinBoolType: BoolCallResult,
    BuiltinNoneType: NoneCallResult
}
