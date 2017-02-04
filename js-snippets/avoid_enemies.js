function costCallback(roomName, costMatrix) {
    if (Memory.enemy_rooms.includes(roomName)) {
        for (let x = 0; x < 50; x += 49) {
            for (let y = 0; y < 50; y++) {
                costMatrix.set(x, y, 255)
            }
        }
        for (let y = 0; y < 50; y += 49) {
            for (let x = 0; x < 50; x++) {
                costMatrix.set(x, y, 255)
            }
        }
    }
}

function pollRooms() {
    for (let name in Game.rooms) {
        room = Game.rooms[name];
        if (room.controller && room.controller.owner && !room.controller.my) {
            if (!Memory.enemy_rooms.includes(name)) {
                Memory.enemy_rooms.push(name);
            }
        }
    }
}
