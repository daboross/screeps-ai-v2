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

        // The following are my own additions!
        // default:
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

        Creep.prototype.hasBodyparts = function (type) {
            for (var i = this.body.length; i-- > 0;) {
                var x = this.body[i];
                if (x.type == type) {
                    return true;
                }
            }
            return false;
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

        setup = true;
    }
};
