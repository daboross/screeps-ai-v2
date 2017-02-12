"use strict";
function activateCustomizations() {
    "use strict";
    // Created by @gdborton on GitHub, available at https://github.com/gdborton/screeps-perf/blob/master/screeps-perf.js
    Array.prototype.filter = function (callback, thisArg) {
        var results = [];
        var arr = this;
        for (var iterator = 0; iterator < arr.length; iterator++) {
            if (callback.call(thisArg, arr[iterator], iterator, arr)) {
                results.push(arr[iterator]);
            }
        }
        return results;
    };

    // Created by @gdborton on GitHub, available at https://github.com/gdborton/screeps-perf/blob/master/screeps-perf.js
    Array.prototype.forEach = function (callback, thisArg) {
        var arr = this;
        for (var iterator = 0; iterator < arr.length; iterator++) {
            callback.call(thisArg, arr[iterator], iterator, arr);
        }
    };

    // Created by @gdborton on GitHub, available at https://github.com/gdborton/screeps-perf/blob/master/screeps-perf.js
    Array.prototype.map = function (callback, thisArg) {
        var arr = this;
        var returnVal = [];
        for (var iterator = 0; iterator < arr.length; iterator++) {
            returnVal.push(callback.call(thisArg, arr[iterator], iterator, arr));
        }
        return returnVal;
    };

    // Default Creep.prototype.getActiveBodyparts:
    // function (type) {
    //     return _.filter(this.body, i => i.hits > 0 && i.type == type).length;
    // }
    Creep.prototype.getActiveBodyparts = function (type) {
        var total = 0;
        for (var i = this.body.length; i-- > 0;) {
            var x = this.body[i];
            if (x.hits <= 0) {
                break;
            }
            if (x.type == type) {
                total += 1;
            }
        }
        return total;
    };

    // Custom addition
    Creep.prototype.hasActiveBodyparts = function (type) {
        for (var i = this.body.length; i-- > 0;) {
            var x = this.body[i];
            if (x.hits <= 0) {
                break;
            }
            if (x.type == type) {
                return true;
            }
        }
        return false;
    };

    // Custom addition
    Creep.prototype.hasActiveBoostedBodyparts = function (type) {
        for (var i = this.body.length; i-- > 0;) {
            var x = this.body[i];
            if (x.hits <= 0) {
                break;
            }
            if (x.boost !== undefined && x.type == type) {
                return true;
            }
        }
        return false;
    };

    // Custom addition
    Creep.prototype.hasActiveOffenseBodyparts = function () {
        for (var i = this.body.length; i-- > 0;) {
            var x = this.body[i];
            if (x.hits <= 0) {
                break;
            }
            if (x.type == ATTACK || x.type == RANGED_ATTACK) {
                return true;
            }
        }
        return false;
    };

    // Custom addition
    Creep.prototype.getBodyparts = function (type) {
        var total = 0;
        for (var i = this.body.length; i-- > 0;) {
            var x = this.body[i];
            if (x.type == type) {
                total += 1;
            }
        }
        return total;
    };

    // Custom addition
    Creep.prototype.hasBodyparts = function (type) {
        for (var i = this.body.length; i-- > 0;) {
            var x = this.body[i];
            if (x.type == type) {
                return true;
            }
        }
        return false;
    };

    // Custom addition
    Creep.prototype.getActiveBodypartsBoostEquivalent = function (type, action) {
        var total = 0;
        var typeBoosts, boostPowers, actionPower;

        typeBoosts = BOOSTS[type];
        for (var i = this.body.length; i-- > 0;) {
            var x = this.body[i];
            if (x.hits <= 0) {
                break;
            }
            if (x.type == type) {
                if (x.boost !== undefined && typeBoosts !== undefined) {
                    boostPowers = typeBoosts[x.boost];
                    if (boostPowers !== undefined) {
                        actionPower = boostPowers[action];
                        if (actionPower !== undefined) {
                            total += actionPower;
                        } else {
                            total += 1;
                        }
                    } else {
                        total += 1;
                    }
                } else {
                    total += 1;
                }
            }
        }
        return total;
    };

    // Custom addition
    Creep.prototype.getBodypartsBoostEquivalent = function (type, action) {
        var total = 0;
        var typeBoosts, boostPowers, actionPower;

        typeBoosts = BOOSTS[type];
        for (var i = this.body.length; i-- > 0;) {
            var x = this.body[i];
            if (x.type == type) {
                if (x.boost !== undefined && typeBoosts !== undefined) {
                    boostPowers = typeBoosts[x.boost];
                    if (boostPowers !== undefined) {
                        actionPower = boostPowers[action];
                        if (actionPower !== undefined) {
                            total += actionPower;
                        } else {
                            total += 1;
                        }
                    } else {
                        total += 1;
                    }
                } else {
                    total += 1;
                }
            }
        }
        return total;
    };

    // Default RoomPosition.prototype.isNearTo:
    // function (firstArg, secondArg) {
    //     var _utils$fetchXYArgumen9 = utils.fetchXYArguments(firstArg, secondArg, globals);
    //
    //     var _utils$fetchXYArgumen10 = _slicedToArray(_utils$fetchXYArgumen9, 3);
    //
    //     var x = _utils$fetchXYArgumen10[0];
    //     var y = _utils$fetchXYArgumen10[1];
    //     var roomName = _utils$fetchXYArgumen10[2];
    //
    //     return abs(x - this.x) <= 1 && abs(y - this.y) <= 1 && (!roomName || roomName == this.roomName);
    // }
    RoomPosition.prototype.isNearTo = function (arg1, arg2) {
        if (arg2 == undefined) {
            if (arg1.pos) {
                arg1 = arg1.pos;
            }
            return Math.abs(arg1.x - this.x) <= 1 && Math.abs(arg1.y - this.y) <= 1 && arg1.roomName == this.roomName;
        } else {
            return Math.abs(arg1 - this.x) <= 1 && Math.abs(arg2 - this.y) <= 1;
        }
    };

    // Default RoomPosition.prototype.isEqualTo:
    // function (firstArg, secondArg) {
    //     var _utils$fetchXYArgumen15 = utils.fetchXYArguments(firstArg, secondArg, globals);
    //
    //     var _utils$fetchXYArgumen16 = _slicedToArray(_utils$fetchXYArgumen15, 3);
    //
    //     var x = _utils$fetchXYArgumen16[0];
    //     var y = _utils$fetchXYArgumen16[1];
    //     var roomName = _utils$fetchXYArgumen16[2];
    //
    //     return x == this.x && y == this.y && (!roomName || roomName == this.roomName);
    // }
    RoomPosition.prototype.isEqualTo = function (arg1, arg2) {
        if (arg2 == undefined) {
            if (arg1 == undefined) {
                return false;
            }
            if (arg1.pos) {
                arg1 = arg1.pos;
            }
            return arg1.x == this.x && arg1.y == this.y && arg1.roomName == this.roomName;
        } else {
            return arg1 == this.x && arg2 == this.y;
        }
    };


    // Default RoomPosition.prototype.inRangeTo:
    // function (firstArg, secondArg, thirdArg) {
    //     var x = firstArg,
    //         y = secondArg,
    //         range = thirdArg,
    //         roomName = this.roomName;
    //     if (_.isUndefined(thirdArg)) {
    //         var pos = firstArg;
    //         if (pos.pos) {
    //             pos = pos.pos;
    //         }
    //         x = pos.x;
    //         y = pos.y;
    //         roomName = pos.roomName;
    //         range = secondArg;
    //     }
    //
    //     return abs(x - this.x) <= range && abs(y - this.y) <= range && roomName == this.roomName;
    // }
    RoomPosition.prototype.inRangeTo = function (arg1, arg2, arg3) {
        if (arg3 === undefined) {
            if (arg1.pos) {
                arg1 = arg1.pos;
            }
            return Math.abs(arg1.x - this.x) <= arg2 && Math.abs(arg1.y - this.y) <= arg2 && arg1.roomName == this.roomName;
        } else {
            return Math.abs(arg1 - this.x) <= arg3 && Math.abs(arg2 - this.y) <= arg3;
        }
    };

    // Default RoomPosition.prototype.getRangeTo:
    // function (firstArg, secondArg) {
    //     var _utils$fetchXYArgumen17 = utils.fetchXYArguments(firstArg, secondArg, globals);
    //
    //     var _utils$fetchXYArgumen18 = _slicedToArray(_utils$fetchXYArgumen17, 3);
    //
    //     var x = _utils$fetchXYArgumen18[0];
    //     var y = _utils$fetchXYArgumen18[1];
    //     var roomName = _utils$fetchXYArgumen18[2];
    //
    //     if (roomName && roomName != this.roomName) {
    //         return Infinity;
    //     }
    //     return max(abs(this.x - x), abs(this.y - y));
    // }
    RoomPosition.prototype.getRangeTo = function (arg1, arg2) {
        if (arg2 === undefined) {
            if (arg1.pos) {
                arg1 = arg1.pos;
            }
            if (arg1.roomName && arg1.roomName != this.roomName) {
                return Infinity;
            }
            return Math.max(Math.abs(this.x - arg1.x), Math.abs(this.y - arg1.y));
        } else {
            return Math.max(Math.abs(this.x - arg1), Math.abs(this.y - arg2));
        }
    };

    // PathFinding functions:

    const directionToDxDy = function (dir) {
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
    };

    const dxDyToDirection = function (dx, dy) {
        if (dx < 0) {
            if (dy < 0) {
                return TOP_LEFT;
            } else if (dy > 0) {
                return BOTTOM_LEFT;
            } else {
                return LEFT;
            }
        } else if (dx > 0) {
            if (dy < 0) {
                return TOP_RIGHT;
            } else if (dy > 0) {
                return BOTTOM_RIGHT;
            } else {
                return RIGHT;
            }
        } else {
            if (dy < 0) {
                return TOP;
            } else if (dy > 0) {
                return BOTTOM;
            } else {
                // both dx and dy are 0!
                return null;
            }
        }
    };

    /**
     * Searches for a path using PathFinder and the given opts, turns the path into a Room.findPath-compatible
     * serialized result, and returns that result.
     *
     * Please ensure that all arguments have been validated when passing in, and that targetPos is a raw position
     * (not a RoomObject with a pos property).
     */
    const findPathPathFinder = function (originPos, targetPos, options) {
        const result = PathFinder.search(
            originPos,
            {
                pos: targetPos,
                range: 'range' in options ? options.range : 1,
            },
            options
        );

        const path = result.path;
        var resultStringArray = []; // it's faster to use [...].join('') than to continuously add to a string iirc.
        var roomToConvert = originPos.roomName;

        if (path.length < 1) {
            return '';
        }

        // The serialized format starts with the _second_ position's x and y values, then the direction from the
        // first pos to second, then direction from second to third, etc. originPos is the first pos, input[0] is
        // the second, input[1] is the third, etc.

        if (path[0].x > 9) {
            resultStringArray.push(path[0].x);
        } else {
            resultStringArray.push(0, path[0].x); // 0-pad
        }
        if (path[0].y > 9) {
            resultStringArray.push(path[0].y);
        } else {
            resultStringArray.push(0, path[0].y); // 0-pad
        }

        var last_x = originPos.x;
        var last_y = originPos.y;
        var pos, dx, dy;
        for (var i = 0; i < path.length; i++) {
            pos = path[i];
            dx = pos.x - last_x;
            dy = pos.y - last_y;
            if (dx === -49) {
                dx = 1;
            } else if (dx === 49) {
                dx = -1;
            }
            if (dy === -49) {
                dy = 1;
            } else if (dy === 49) {
                dy = -1;
            }

            resultStringArray.push(dxDyToDirection(dx, dy));
            if (pos.roomName != roomToConvert) {
                break;
            }
            last_x = pos.x;
            last_y = pos.y;
        }
        return resultStringArray.join('');
    };

    // Default Creep.prototype.moveByPath:
    // function (path) {
    //     if (_.isArray(path) && path.length > 0 && path[0] instanceof globals.RoomPosition) {
    //         var idx = _.findIndex(path, i => i.isEqualTo(this.pos));
    //         if (idx === -1) {
    //             if (!path[0].isNearTo(this.pos)) {
    //                 return C.ERR_NOT_FOUND;
    //             }
    //         }
    //         idx++;
    //         if (idx >= path.length) {
    //             return C.ERR_NOT_FOUND;
    //         }
    //
    //         return this.move(this.pos.getDirectionTo(path[idx]));
    //     }
    //
    //     if (_.isString(path)) {
    //         path = utils.deserializePath(path);
    //     }
    //     if (!_.isArray(path)) {
    //         return C.ERR_INVALID_ARGS;
    //     }
    //     var cur = _.find(path, i => i.x - i.dx == this.pos.x && i.y - i.dy == this.pos.y);
    //     if (!cur) {
    //         return C.ERR_NOT_FOUND;
    //     }
    //
    //     return this.move(cur.direction);
    // }
    Creep.prototype.__moveByPath = Creep.prototype.moveByPath;
    Creep.prototype.moveByPath = function (path) {
        if (!_.isString(path)) {
            return this.__moveByPath(path);
        }
        var path_len = path.length;
        if (path_len < 5) {
            return ERR_NOT_FOUND;
        }
        var my_x = this.pos.x, my_y = this.pos.y;
        var x_to_check = +path.slice(0, 2);
        var y_to_check = +path.slice(2, 4);
        var dir, dxdy;
        // The path serialization format basically starts with the second position x, second position y, and then
        // follows with a list of directions *to get to each position*. To clarify, the first direction, at idx=4,
        // gives the direction *from the first position to the second position*. So, to find the first position,
        // we subtract that! I do think this is actually more performant than trying to do any more complicated
        // logic in the loop.
        dxdy = directionToDxDy(+path[4]);
        x_to_check -= dxdy[0];
        y_to_check -= dxdy[1];
        // Since we start at 4 again, we'll be re-adding what we just subtracted above - this lets us check both the
        // first and second positions correctly!
        for (var idx = 4; idx < path_len; idx++) {
            // Essentially at this point, *_to_check represent the point reached by the *last* movement (the pos
            // reached by the movement at (idx - 1) since idx just got incremented at the start of this loop)
            // Also, if this is the first iteration and x/y_to_check match the first pos, idx is at 4, the fifth
            // pos, directly after the initial x/y, and also the first direction to go!
            if (x_to_check === my_x && y_to_check == my_y) {
                // console.log(`[${this.memory.home}][${this.name}] Found my position (${my_x}, ${my_y})`);
                dir = +path[idx];
                return this.move(dir);
            } else {
                // console.log(`[${this.memory.home}][${this.name}] Not my position: (${x_to_check}, ${y_to_check})`);
            }
            dxdy = directionToDxDy(+path[idx]);
            if (dxdy === null) {
                console.log(`Unknown direction! couldn't figure out '${path[idx]}'`);
                return ERR_INVALID_ARGS;
            }
            x_to_check += dxdy[0];
            y_to_check += dxdy[1];
        }
        return ERR_NOT_FOUND;
    };

    // Default Creep.prototype.moveTo:
    // function (firstArg, secondArg, opts) {
    //
    //     if (!this.my) {
    //         return C.ERR_NOT_OWNER;
    //     }
    //     if (this.spawning) {
    //         return C.ERR_BUSY;
    //     }
    //     if (data(this.id).fatigue > 0) {
    //         return C.ERR_TIRED;
    //     }
    //     if (this.getActiveBodyparts(C.MOVE) == 0) {
    //         return C.ERR_NO_BODYPART;
    //     }
    //
    //     var _utils$fetchXYArgumen = utils.fetchXYArguments(firstArg, secondArg, globals);
    //
    //     var _utils$fetchXYArgumen2 = _slicedToArray(_utils$fetchXYArgumen, 3);
    //
    //     var x = _utils$fetchXYArgumen2[0];
    //     var y = _utils$fetchXYArgumen2[1];
    //     var roomName = _utils$fetchXYArgumen2[2];
    //
    //     roomName = roomName || this.pos.roomName;
    //     if (_.isUndefined(x) || _.isUndefined(y)) {
    //         register.assertTargetObject(firstArg);
    //         return C.ERR_INVALID_TARGET;
    //     }
    //
    //     var targetPos = new globals.RoomPosition(x, y, roomName);
    //
    //     if (_.isObject(firstArg)) {
    //         opts = _.clone(secondArg);
    //     }
    //     opts = opts || {};
    //
    //     if (_.isUndefined(opts.reusePath)) {
    //         opts.reusePath = 5;
    //     }
    //     if (_.isUndefined(opts.serializeMemory)) {
    //         opts.serializeMemory = true;
    //     }
    //
    //     if (x == this.pos.x && y == this.pos.y && roomName == this.pos.roomName) {
    //         return C.OK;
    //     }
    //
    //     if (opts.reusePath && this.memory && _.isObject(this.memory) && this.memory._move) {
    //
    //         var _move = this.memory._move;
    //
    //         if (runtimeData.time > _move.time + parseInt(opts.reusePath) || _move.room != this.pos.roomName) {
    //             delete this.memory._move;
    //         } else if (_move.dest.room == roomName && _move.dest.x == x && _move.dest.y == y) {
    //
    //             var path = _.isString(_move.path) ? utils.deserializePath(_move.path) : _move.path;
    //
    //             var idx = _.findIndex(path, { x: this.pos.x, y: this.pos.y });
    //             if (idx != -1) {
    //                 var oldMove = _.cloneDeep(_move);
    //                 path.splice(0, idx + 1);
    //                 try {
    //                     _move.path = opts.serializeMemory ? utils.serializePath(path) : path;
    //                 } catch (e) {
    //                     console.log('$ERR', this.pos, x, y, roomName, JSON.stringify(path), '-----', JSON.stringify(oldMove));
    //                     throw e;
    //                 }
    //             }
    //             if (path.length == 0) {
    //                 return this.pos.isNearTo(targetPos) ? C.OK : C.ERR_NO_PATH;
    //             }
    //             var result = this.moveByPath(path);
    //
    //             if (result == C.OK) {
    //                 return C.OK;
    //             }
    //         }
    //     }
    //
    //     if (opts.noPathFinding) {
    //         return C.ERR_NOT_FOUND;
    //     }
    //
    //     var path = this.pos.findPathTo(targetPos, opts);
    //
    //     if (opts.reusePath && this.memory && _.isObject(this.memory)) {
    //         this.memory._move = {
    //             dest: { x, y, room: roomName },
    //             time: runtimeData.time,
    //             path: opts.serializeMemory ? utils.serializePath(path) : _.clone(path),
    //             room: this.pos.roomName
    //         };
    //     }
    //
    //     if (path.length == 0) {
    //         return C.ERR_NO_PATH;
    //     }
    //     this.move(path[0].direction);
    //     return C.OK;
    // }
    Creep.prototype.__moveTo = Creep.prototype.moveTo;

    /**
     * Custom replacement of moveTo, which just calls moveTo unless a 'roomCallback' argument is passed in in the
     * options. The memory format this function uses is identical to the default moveTo's, so it is supported
     * alternate* calling this function with and without the 'roomCallback' option.
     *
     * When passed roomCallback, this function:
     * - assumes that Creep.prototype.moveByPath has already been optimized to deal with
     *   serialized paths, and will pass it purely serialized paths.
     * - does not accept the 'serializeMemory' option, and will always assume it is set to true
     * - does not accept any of the 'costCallback', 'ignoreCreeps', 'ignoreRoads' or 'ignoreDestructibleStructures'
     *   options. (note: roomCallback is used by PathFinder instead of the costCallback used by findPath)
     * - passes all arguments on to PathFinder.search as is.
     * - accepts one additional option, 'range', which is passed into PathFinder as part of the target object.
     */
    Creep.prototype.moveTo = function (arg1, arg2, arg3) {
        var targetPos, opts;
        if (arg3 === undefined) {
            if (arg1.pos) {
                arg1 = arg1.pos;
            }
            targetPos = arg1;
            opts = arg2 || {};
        } else {
            targetPos = new RoomPosition(arg1, arg2, this.pos.roomName);
            opts = arg3 || {};
        }

        if (!('roomCallback' in opts)) {
            return this.__moveTo(arg1, arg2, arg3); // Compatible memory format.
        }
        if (!_.isNumber(targetPos.x) || !_.isNumber(targetPos.y) || !_.isString(targetPos.roomName)) {
            return ERR_INVALID_TARGET;
        }
        if (!_.isObject(opts)) {
            return ERR_INVALID_ARGS;
        }
        if (!this.my) {
            return ERR_NOT_OWNER;
        }
        if (this.spawning) {
            return ERR_BUSY
        }
        if (this.fatigue > 0) {
            return ERR_TIRED
        }
        if (!this.hasActiveBodyparts(MOVE)) {
            return ERR_NO_BODYPART;
        }

        if (this.pos.isNearTo(targetPos)) {
            if (this.pos.isEqualTo(targetPos)) {
                return OK;
            } else {
                return this.move(this.pos.getDirectionTo(targetPos));
            }
        }

        const reusePath = _.isObject(this.memory) && ('reusePath' in opts ? opts.reusePath : 5);

        if (reusePath) {
            var _move = this.memory._move;

            if (_.isObject(_move)
                && Game.time <= _move.time + Number(reusePath)
                && _move.room == this.pos.roomName
                && _move.dest.room == targetPos.roomName
                && _move.dest.x == targetPos.x
                && _move.dest.y == targetPos.y) {

                // moveByPath is optimized to deal with serialized paths already, and it's more CPU to
                // re-serialize each tick with a smaller string than it is to store the larger string the
                // whole time.
                var byPathResult = this.moveByPath(_move.path);
                if (byPathResult !== ERR_NOT_FOUND && byPathResult !== ERR_INVALID_ARGS
                    && byPathResult !== ERR_NO_PATH) {
                    return byPathResult;
                }
            }
        }

        if (opts.noPathFinding) {
            return ERR_NOT_FOUND;
        }

        // This uses PathFinder, and returns the result as an already-serialized path.
        const path = findPathPathFinder(this.pos, targetPos, opts);

        if (reusePath) {
            this.memory._move = {
                dest: {
                    x: targetPos.x,
                    y: targetPos.y,
                    room: targetPos.roomName,
                },
                time: Game.time,
                path: path,
                room: this.pos.roomName,
            }
        }

        return this.moveByPath(path);
    };

    global.__customizations_active = true;
}

if (!global.__customizations_active) {
    activateCustomizations()
}
