function is_block_clear(room, x, y) {
    if (x > 49 || y > 49 || x < 0 || y < 0) {
        return false;
    }
    if (Game.map.getTerrainAt (x, y, room.room.name) == 'wall') {
        return false;
    }
    if (room.lookFoAt(LOOK_CREEPS, x, y).length != 0) {
        return false;
    }
    var structures = room.lookForAt(LOOK_STRUCTURES, x, y);
    for (var i = 0; i < structures.length; i++) {
        var struct = structures[i];
        if ((struct.structureType != STRUCTURE_RAMPART || !(struct.my))
                && struct.structureType != STRUCTURE_CONTAINER
                && struct.structureType != STRUCTURE_ROAD) {
            return false;
        }
    }
    var construction_sites = room.lookForAt(LOOK_CONSTRUCTION_SITES, x, y);
    for (var i = 0; i < construction_sites.length; i++) {
        var site = construction_sites[i];
        if (site.my
                && site.structureType != STRUCTURE_RAMPART
                && site.structureType != STRUCTURE_CONTAINER
                && site.structureType != STRUCTURE_ROAD) {
            return false;
        }
    }
    return true;
};
