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

        // This one is my own addition!
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

        setup = true;
    }
};
