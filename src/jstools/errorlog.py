from jstools.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


def report_error(place, err, description):
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