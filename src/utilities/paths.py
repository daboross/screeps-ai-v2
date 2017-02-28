from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')


def direction_to_dx_dy(dir):
    """
    :type dir: int
    :rtype: (int, int)
    """
    __pragma__('js', '{}', """
    switch (dir) {
        case TOP:
            return [0, -1];
        case TOP_RIGHT:
            return [1, -1];
        case RIGHT:
            return [1, 0];
        case BOTTOM_RIGHT:
            return [1, 1];
        case BOTTOM:
            return [0, 1];
        case BOTTOM_LEFT:
            return [-1, 1];
        case LEFT:
            return [-1, 0];
        case TOP_LEFT:
            return [-1, -1];
        default:
            return null;
    }
""")
