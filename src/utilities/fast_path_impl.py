"""
This file implements a replacement for Creep.prototype.moveByPath.

The original method is as follows:

function (path) {
    if (_.isArray(path) && path.length > 0 && path[0] instanceof globals.RoomPosition) {
        var idx = _.findIndex(path, i => i.isEqualTo(this.pos));
        if (idx === -1) {
            if (!path[0].isNearTo(this.pos)) {
                return C.ERR_NOT_FOUND;
            }
        }
        idx++;
        if (idx >= path.length) {
            return C.ERR_NOT_FOUND;
        }

        return this.move(this.pos.getDirectionTo(path[idx]));
    }

    if (_.isString(path)) {
        path = utils.deserializePath(path);
    }
    if (!_.isArray(path)) {
        return C.ERR_INVALID_ARGS;
    }
    var cur = _.find(path, i => i.x - i.dx == this.pos.x && i.y - i.dy == this.pos.y);
    if (!cur) {
        return C.ERR_NOT_FOUND;
    }

    return this.move(cur.direction);
}
"""
