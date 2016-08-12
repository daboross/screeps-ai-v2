import flags
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')

_flag_sub_to_structure_type = {
    flags.SUB_SPAWN: STRUCTURE_SPAWN,
    flags.SUB_EXTENSION: STRUCTURE_EXTENSION,
    flags.SUB_RAMPART: STRUCTURE_RAMPART,
    flags.SUB_WALL: STRUCTURE_WALL,
    flags.SUB_STORAGE: STRUCTURE_STORAGE,
    flags.SUB_TOWER: STRUCTURE_TOWER,
    flags.SUB_LINK: STRUCTURE_LINK,
}


class ConstructionMind:
    """
    :type room: control.hivemind.RoomMind
    :type hive: control.hivemind.HiveMind
    """

    def __init__(self, room):
        """
        :type room: control.hivemind.RoomMind
        :param room:
        """
        self.room = room
        self.hive = room.hive_mind

    def toString(self):
        return "ConstructionMind[room: {}]".format(self.room.room_name)

    def _get_mem(self):
        if self.room.room.memory.construction is undefined:
            self.room.room.memory.construction = {}
        return self.room.room.memory.construction

    mem = property(_get_mem)

    def get_cached_property(self, name):
        if name in self.mem and self.mem[name].dead_at > Game.time:
            return self.mem[name].value
        else:
            return None

    def store_cached_property(self, name, value, ttl):
        self.mem[name] = {"value": value, "dead_at": Game.time + ttl}

    def refresh_targets(self):
        del self.mem.next_targets

    def next_priority_construction_targets(self):
        priority_list = self.get_cached_property("next_targets")
        if priority_list is not None:
            return priority_list

        current_targets = {}
        low_priority = []
        med_priority = []
        high_priority = []

        for site in self.room.room.find(FIND_CONSTRUCTION_SITES):
            if site.structureType in (STRUCTURE_SPAWN, STRUCTURE_EXTENSION, STRUCTURE_TOWER):
                high_priority.append(site.id)
            elif site.structureType in (STRUCTURE_WALL, STRUCTURE_RAMPART, STRUCTURE_STORAGE, STRUCTURE_LINK):
                med_priority.append(site.id)
            else:
                low_priority.append(site.id)
            if current_targets[site.structureType]:
                current_targets[site.structureType] += 1
            else:
                current_targets[site.structureType] = 1

        if self.room.spawn:
            spawn_pos = self.room.spawn.pos
        else:
            spawn_flag = flags.find_ms_flag(self.room, flags.MAIN_BUILD, flags.SUB_SPAWN)
            if len(spawn_flag):
                spawn_pos = spawn_flag[0].pos
            else:
                print("[{}][building] Warning: Finding construction targets for room {},"
                      " which has no spawn planned!".format(self.room.room_name, self.room.room_name))
                spawn_pos = __new__(RoomPosition(25, 25, self.room.room_name))

        if self.room.room.controller and self.room.room.controller.my:
            controller_level = self.room.room.controller.level
        else:
            print("[{}][building] Warning: finding construction targets for room {},"
                  " which isn't ours!".format(self.room.room_name, self.room.room_name))
            controller_level = 0

        new_site_placed = False

        currently_built_structures = {}

        for flag, flag_type in _.sortBy(
                flags.find_by_main_with_sub(self.room, flags.MAIN_BUILD),
                lambda flag_tuple: movement.distance_squared_room_pos(spawn_pos, flag_tuple[0].pos)):
            structure_type = _flag_sub_to_structure_type[flag_type]
            if not structure_type:
                print("[{}][building] Warning: structure type corresponding to flag type {} not found!".format(
                    self.room.room_name, flag_type
                ))
            if currently_built_structures[structure_type]:
                currently_built = currently_built_structures[structure_type]
            else:
                currently_built = len(self.room.room.find(FIND_STRUCTURES, {
                    "filter": lambda s: s.structureType == structure_type and s.my != False
                }))
                currently_built_structures[structure_type] = currently_built
            if CONTROLLER_STRUCTURES[structure_type][controller_level] \
                    > currently_built + (current_targets[structure_type] or 0):
                if len(_.filter(flag.pos.lookFor(LOOK_STRUCTURES), {"structureType": structure_type})) \
                        or len(_.filter(flag.pos.lookFor(LOOK_CONSTRUCTION_SITES), {"structureType": structure_type})):
                    continue  # already built.
                flag.pos.createConstructionSite(structure_type)
                if structure_type in (STRUCTURE_SPAWN, STRUCTURE_EXTENSION, STRUCTURE_TOWER):
                    high_priority.append("flag-{}".format(flag.name))
                elif structure_type in (STRUCTURE_WALL, STRUCTURE_RAMPART, STRUCTURE_STORAGE, STRUCTURE_LINK):
                    med_priority.append("flag-{}".format(flag.name))
                else:
                    low_priority.append("flag-{}".format(flag.name))
                new_site_placed = True

        if len(high_priority):
            # We're going to want to work on high priority targets anyways, even if new ones are placed. Long TTL!
            self.store_cached_property("next_targets", high_priority, 400)
        elif len(med_priority):
            # We're halfway done. Somewhat random TTL!
            self.store_cached_property("next_targets", med_priority, 200)
        elif len(low_priority):
            # These are the last of the targets placed - there won't be any more unless more are placed manually.
            # TODO: This should be lower if auto-placing is ever implemented. Or, autoplacing should just use refresh()
            self.store_cached_property("next_targets", low_priority, 300)
        else:
            # No targets available at current controller level. TODO: refresh when controller upgrades!
            self.store_cached_property("next_targets", low_priority, 70)

        if new_site_placed:
            # expires in one tick, when new construction sites are active.
            self.mem.next_targets.dead_at = Game.time + 1

        return self.get_cached_property("next_targets")


profiling.profile_whitelist(ConstructionMind, "refresh_targets")
