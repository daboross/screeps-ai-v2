"use strict";
// Credit to @gdborton on GitHub.
// Copied from https://github.com/gdborton/screeps-perf/blob/master/screeps-perf.js.

var originalFindPath = Room.prototype.findPath;
var setup = false;

module.exports = function (options) {
    if (!setup) {
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

        Array.prototype.forEach = function (callback, thisArg) {
            var arr = this;
            for (var iterator = 0; iterator < arr.length; iterator++) {
                callback.call(thisArg, arr[iterator], iterator, arr);
            }
        };

        Array.prototype.map = function (callback, thisArg) {
            var arr = this;
            var returnVal = [];
            for (var iterator = 0; iterator < arr.length; iterator++) {
                returnVal.push(callback.call(thisArg, arr[iterator], iterator, arr));
            }
            return returnVal;
        };

        setup = true;

        /** The following are my own additions!
         * default:
         * function (type) {
         *     return _.filter(this.body, i => i.hits > 0 && i.type == type).length;
         * }
         */
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

        Creep.prototype.hasBodyparts = function (type) {
            for (var i = this.body.length; i-- > 0;) {
                var x = this.body[i];
                if (x.type == type) {
                    return true;
                }
            }
            return false;
        };

        Creep.prototype.getActiveBodypartsBoostEquivalent = function (type, action) {
            var total = 0;
            for (var i = this.body.length; i-- > 0;) {
                var x = this.body[i];
                if (x.hits <= 0) {
                    break;
                }
                if (x.type == type) {
                    if (x.boost !== undefined) {
                        total += BOOSTS[type][x.boost][action];
                    } else {
                        total += 1;
                    }
                }
            }
            return total;
        };

        Creep.prototype.getBodypartsBoostEquivalent = function (type, action) {
            var total = 0;
            for (var i = this.body.length; i-- > 0;) {
                var x = this.body[i];
                if (x.type == type) {
                    if (x.boost !== undefined) {
                        total += BOOSTS[type][x.boost][action];
                    } else {
                        total += 1;
                    }
                }
            }
            return total;
        };

        // default:
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

        // default:
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


        // default:
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

        // default:
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

        // PathFinding
        var mbspUtilDirToXY = function (dir) {
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

        // default moveByPath:
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
        Creep.prototype.moveBySerializedPath = function (path) {
            if (!_.isString(path)) {
                return ERR_INVALID_ARGS;
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
            dxdy = mbspUtilDirToXY(+path[4]);
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
                dxdy = mbspUtilDirToXY(+path[idx]);
                if (dxdy === null) {
                    console.log(`Unknown direction! couldn't figure out '${path[idx]}'`);
                    return ERR_INVALID_ARGS;
                }
                x_to_check += dxdy[0];
                y_to_check += dxdy[1];
            }
            return ERR_NOT_FOUND;
        };
        Creep.prototype.defaultMoveByPath = Creep.prototype.moveByPath;
        Creep.prototype.moveByPath = function (path) {
            if (_.isString(path)) {
                return this.moveBySerializedPath(path);
            } else {
                return this.defaultMoveByPath(path);
            }
        };

        // default moveTo:
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

        // default pos.findPathTo:
        // RoomPosition.prototype.findPathTo = register.wrapFn(function(firstArg, secondArg, opts) {
        //
        //     var [x,y,roomName] = utils.fetchXYArguments(firstArg, secondArg, globals),
        //         room = register.rooms[this.roomName];
        //
        //     if(_.isObject(secondArg)) {
        //         opts = _.clone(secondArg);
        //     }
        //     opts = opts || {};
        //
        //     roomName = roomName || this.roomName;
        //
        //     if(!room) {
        //         throw new Error(`Could not access room ${this.roomName}`);
        //     }
        //
        //     if(roomName == this.roomName || register._useNewPathFinder) {
        //         return room.findPath(this, new globals.RoomPosition(x,y,roomName), opts);
        //     }
        //     else {
        //         var exitDir = room.findExitTo(roomName);
        //         if(exitDir < 0) {
        //             return [];
        //         }
        //         var exit = this.findClosestByPath(exitDir, opts);
        //         if(!exit) {
        //             return [];
        //         }
        //         return room.findPath(this, exit, opts);
        //     }
        //
        // });

        // default room.findPath:
        // function _findPath2(id, fromPos, toPos, opts) {
        //     opts = opts || {};
        //
        //     if(fromPos.isEqualTo(toPos)) {
        //         return opts.serialize ? '' : [];
        //     }
        //
        //     if(opts.avoid) {
        //         register.deprecated('`avoid` option cannot be used when `PathFinder.use()` is enabled. Use `costCallback` instead.');
        //         opts.avoid = undefined;
        //     }
        //     if(opts.ignore) {
        //         register.deprecated('`ignore` option cannot be used when `PathFinder.use()` is enabled. Use `costCallback` instead.');
        //         opts.ignore = undefined;
        //     }
        //     if(opts.maxOps === undefined && (opts.maxRooms === undefined || opts.maxRooms > 1) && fromPos.roomName != toPos.roomName) {
        //         opts.maxOps = 20000;
        //     }
        //     var searchOpts = {
        //         roomCallback: function(roomName) {
        //             var costMatrix = getPathfindingGrid2(roomName, opts);
        //             if(typeof opts.costCallback == 'function') {
        //                 costMatrix = costMatrix.clone();
        //                 var resultMatrix = opts.costCallback(roomName, costMatrix);
        //                 if(resultMatrix instanceof globals.PathFinder.CostMatrix) {
        //                     costMatrix = resultMatrix;
        //                 }
        //             }
        //             return costMatrix;
        //         },
        //         maxOps: opts.maxOps,
        //         maxRooms: opts.maxRooms
        //     };
        //     if(!opts.ignoreRoads) {
        //         searchOpts.plainCost = 2;
        //         searchOpts.swampCost = 10;
        //     }
        //
        //     var ret = globals.PathFinder.search(fromPos, {range: Math.max(1,opts.range || 0), pos: toPos}, searchOpts);
        //
        //     if(!opts.range &&
        //             (ret.path.length && ret.path[ret.path.length-1].isNearTo(toPos) && !ret.path[ret.path.length-1].isEqualTo(toPos) ||
        //             !ret.path.length && fromPos.isNearTo(toPos))) {
        //         ret.path.push(toPos);
        //     }
        //     var curX = fromPos.x, curY = fromPos.y;
        //
        //     var resultPath = [];
        //
        //     for(let i=0; i<ret.path.length; i++) {
        //         let pos = ret.path[i];
        //         if(pos.roomName != id) {
        //             break;
        //         }
        //         let result = {
        //             x: pos.x,
        //             y: pos.y,
        //             dx: pos.x - curX,
        //             dy: pos.y - curY,
        //             direction: utils.getDirection(pos.x - curX, pos.y - curY)
        //         };
        //
        //         curX = result.x;
        //         curY = result.y;
        //         resultPath.push(result);
        //     }
        //
        //     if(opts.serialize) {
        //         return utils.serializePath(resultPath);
        //     }
        //
        //     return resultPath;
        // }

        // RoomPosition.prototype.defaultFindPathTo = RoomPosition.prototype.findPathTo;
        // RoomPosition.prototype.findPathTo = function(arg1, arg2, arg3) {
        //     let x, y, roomName, opts;
        //     if (arg3 === undefined) {
        //         if (arg1.pos === undefined) {
        //             x = arg1.x;
        //             y = arg1.y;
        //             roomName = arg1.roomName;
        //         } else {
        //             x = arg1.pos.x;
        //             y = arg1.pos.y;
        //             roomName = arg1.pos.roomName;
        //         }
        //         opts = arg2;
        //     } else {
        //         x = arg1;
        //         y = arg2;
        //         roomName = this.roomName;
        //         opts = arg3;
        //     }
        //     if (!opts['roomCallback']) {
        //         return this.defaultFindPathTo(arg1, arg2, arg3);
        //     }
        //     let searchOpts = {
        //         roomCallback: opts['roomCallback'],
        //     }
        // }
    }
};
