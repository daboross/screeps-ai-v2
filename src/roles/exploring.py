import flags
from constants import target_single_flag, INVADER_USERNAME
from roles.offensive import MilitaryBase
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


class Scout(MilitaryBase):
    def run(self):
        destination = self.targets.get_new_target(self, target_single_flag, flags.SCOUT)
        if not destination:
            if not self.memory.idle_for:
                self.log("WARNING: Scout does not have destination set!")
                self.memory.idle_for = 1
            else:
                self.memory.idle_for += 1
                if self.memory.idle_for >= 10:
                    self.log("Scout idle for 10 ticks, committing suicide.")
                    self.creep.suicide()
            return

        if self.memory.last_room != self.pos.roomName:
            self.memory.last_room = self.pos.roomName
            if self.room.enemy and self.pos.roomName != destination.pos.roomName:
                self.recalc_military_path(self.home.spawn, destination, {"ignore_swamp": True,
                                                                         "use_roads": False})
            rx, ry = movement.parse_room_to_xy(self.pos.roomName)
            rrx = abs(rx) % 10  # TODO: this will break if we ever actually fix parse_room_to_xy making E0S0 == W0N0
            rry = abs(ry) % 10
            if (rrx == 4 or rrx == 5 or rrx == 6) and (rry == 4 or rry == 5 or rry == 6) \
                    and not (rrx == 5 and rry == 5):
                # should be a source keeper room
                if not len(flags.find_flags(self.room, flags.SK_LAIR_SOURCE_NOTED)):
                    lair_count = 0
                    for lair in self.room.find(FIND_HOSTILE_STRUCTURES):
                        if lair.structureType == STRUCTURE_KEEPER_LAIR:
                            if not flags.look_for(self.room, lair, flags.SK_LAIR_SOURCE_NOTED):
                                flags.create_flag(lair, flags.SK_LAIR_SOURCE_NOTED)
                            lair_count += 1
                    if lair_count:
                        for source in self.room.find(FIND_SOURCES).concat(self.room.find(FIND_MINERALS)):
                            if not flags.look_for(self.room, source, flags.SK_LAIR_SOURCE_NOTED):
                                flags.create_flag(source, flags.SK_LAIR_SOURCE_NOTED)
                    else:
                        self.log("WARNING: Scout found no lairs in supposed source keeper room {}! Logic error?"
                                 .format(self.pos.roomName))

            self.hive.honey.generate_serialized_cost_matrix(self.pos.roomName)
            self.log("Scouted room {}, {}.".format(rx, ry))

        if self.pos.isEqualTo(destination) or \
                (self.pos.isNearTo(destination)
                 and not movement.is_block_empty(self.room, destination.pos.x, destination.pos.y)):
            if not self.memory.arrived:
                self.memory.arrived = Game.time
                destination.memory.travel_time = CREEP_LIFE_TIME - self.creep.ticksToLive
                self.log("Arrived at {} ({}), traveling from {} in {} ticks."
                         .format(destination, destination.pos, self.home.spawn, destination.memory.travel_time))
        elif self.pos.isNearTo(destination):
            self.basic_move_to(destination)
        else:
            self.follow_military_path(self.home.spawn, destination, {"ignore_swamp": True,
                                                                     "use_roads": False})
        if self.pos.roomName == destination.pos.roomName and destination.memory.activate_attack_in:
            if len(self.room.defense.dangerous_hostiles()) and _.find(self.room.defense.dangerous_hostiles(),
                                                                      lambda h: h.owner.username != INVADER_USERNAME):
                rooms_newly_activated = []
                for name in destination.memory.activate_attack_in:
                    activate_attack_in = self.hive.get_room(name)
                    if activate_attack_in:
                        if not activate_attack_in.mem.attack:
                            activate_attack_in.mem.attack = True
                            rooms_newly_activated.push(name)
                    else:
                        self.log("WARNING: Couldn't find room {} which flag {} is supposed to alert for attack."
                                 .format(name, destination.name))
                if len(rooms_newly_activated):
                    with_mining_op_shutdowns = _.filter(rooms_newly_activated,
                                                        lambda r: not _.get(Memory,
                                                                            ["rooms", r, "remotes_safe"], False))
                    hostiles = self.room.defense.dangerous_hostiles()
                    message = (
                        "\nDANGER: -----"
                        "\nHostile belonging to player {} detected in room {}. Game time: {}"
                        "\n"
                        "\n{}"
                        "\n"
                        "\nThis has triggered active-defense mode in rooms {}{}."
                        "\nDANGER: -----"
                    ).format(
                        hostiles[0].owner.username,
                        self.pos.roomName,
                        Game.time,
                        "\n".join(["Found hostile with hits {}/{}, owner {}, body [{}]"
                                  .format(h.hits, h.hitsMax, h.owner.username,
                                          [("{}:{}".format(p.boost, p.type) if p.boost else p.type)
                                           for p in h.body]) for h in hostiles]),
                        rooms_newly_activated,
                        (", and shut down mining operations in rooms {}".format(with_mining_op_shutdowns)
                         if len(with_mining_op_shutdowns) else ""),
                    )
                    console.log(message)
                    Game.notify(message)

    def _calculate_time_to_replace(self):
        target = self.targets.get_new_target(self, target_single_flag, flags.SCOUT)
        if not target:
            return -1
        path_len = self.get_military_path_length(self.home.spawn, target, {"ignore_swamp": True,
                                                                           "use_roads": False})
        return path_len + 53  # Body size is always 1.
