const room_regex = new RegExp('(W|E)([0-9]{1,2})(N|S)([0-9]{1,2})');

function parse_room_to_xy(room_name) {
    const matches = room_regex.exec(room_name);
    if (!(matches)) {
        return [0, 0];
    }
    let x, y;
    if (matches [1] == 'W') {
        x = -(Number(matches [2])) - 1;
    }
    else {
        x = +(Number(matches [2]));
    }
    if (matches [3] == 'N') {
        y = -(Number(matches [4])) - 1;
    }
    else {
        y = +(Number(matches [4]));
    }
    return [x, y];
}
function room_xy_to_name(room_x, room_y) {
    return (room_x > 0 ? 'E' : 'W') + (room_x < 0 ? -(room_x) - 1 : room_x) + (room_y > 0 ? 'S' : 'N') + (room_y < 0 ? -(room_y) - 1 : room_y)
}
function chebyshev_distance_room_pos(pos1, pos2) {
    if (pos1.pos) {
        pos1 = pos1.pos;
    }
    if (pos2.pos) {
        pos2 = pos2.pos;
    }
    if (pos1.roomName == pos2.roomName) {
        return max(abs(pos1.x - pos2.x), abs(pos1.y - pos2.y));
    }
    const room_1_pos = parse_room_to_xy(pos1.roomName);
    const room_2_pos = parse_room_to_xy(pos2.roomName);
    const world_pos_1 = [room_1_pos [0] * 49 + pos1.x, room_1_pos [1] * 49 + pos1.y];
    const world_pos_2 = [room_2_pos [0] * 49 + pos2.x, room_2_pos [1] * 49 + pos2.y];
    return Math.max(Math.abs(world_pos_1 [0] - world_pos_2 [0]), Math.abs(world_pos_1 [1] - world_pos_2 [1]));
}
