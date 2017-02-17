function find_an_open_space(room_name) {
    var x = 0;
    var y = 0;
    var dx = 0;
    var dy = -1;
    for (var i = 0; i < 50 * 50; i++) {
        if (Game.map.getTerrainAt(24 + x, 24 + y, room_name) != 'wall') {
            return new RoomPosition(24 + x, 24 + y, room_name);
        }
        if (x == y || x < 0 && x == -(y) || x > 0 && x == -(y) + 1) {
            [dx, dy] = [-dy, dx];
        }
        x += dx;
        y += dy;
    }
    console.log(`[movement] WARNING: Could not find open space in ${room_name}.`);
    return new RoomPosition(25, 25, room_name);
};