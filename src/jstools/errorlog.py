from typing import Any, Callable, TypeVar

from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


def report_error(place: str, err: Any, description: str):
    if err == undefined:
        if err is None:
            err_description = "null error"
        elif err is undefined:
            err_description = "undefined error"
        else:
            err_description = err + " error"
    else:
        if err.stack == undefined:
            err_description = "error has undefined stack: {}".format(err)
        else:
            err_description = "error '{}' has stack:\n{}".format(err, err.stack)

    msg = "[{}][{}] Error: {}\n{}".format(place, Game.time, description, err_description)
    print(msg)
    Game.notify(msg)
    if err == undefined:
        __pragma__('js', 'throw err;')


__pragma__('skip')
_T = TypeVar('_T')
_I = TypeVar('_I')
_O = TypeVar('_O')
__pragma__('noskip')


def try_exec(place: str, thing: Callable[Any, _T], error_description: Callable[Any, str], *args: Any) -> _T:
    result = True
    try:
        result = thing(*args)
    except:
        report_error(place, __except0__, error_description(*args))
    return result


def execute(thing, *args):
    result = None
    try:
        result = thing(*args)
    except:
        report_error(thing.place, __except0__, thing.err_desc(*args))
    return result


def wrapped(place: str, error_description: Callable[_I, str], error_return=True) \
        -> Callable[[Callable[_I, _O]], Callable[_I, _O]]:
    def wrap(thing):
        def new_definition(*args):
            result = error_return
            try:
                result = thing(*args)
            except:
                report_error(place, __except0__, error_description(*args))
            return result

        return new_definition

    return wrap
