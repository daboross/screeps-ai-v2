from constants import INVADER_USERNAME, SCOUT, target_single_flag
from creeps.behaviors.military import MilitaryBase
from empire import stored_data
from jstools.screeps import *
from utilities import movement, positions

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')


class Scout(MilitaryBase):
    def run(self):
        destination = self.targets.get_existing_target(self, target_single_flag)
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

        still_exploring = ('explored_at' not in destination.memory) \
                          or (positions.serialize_pos_xy(destination)
                              + destination.pos.roomName) != destination.memory.explored_at

        recalc = False

        if still_exploring:
            # recalculate_path
            if self.memory.rp:
                self.log("Recalculating path due to circumstances in {}.".format(self.memory.rp))
                self.recalc_military_path(self.home.spawn, destination, {
                    "ignore_swamp": True,
                    "use_roads": False,
                })
                del self.memory.rp

            if self.memory.last_room != self.pos.roomName:
                self.memory.last_room = self.pos.roomName
                if self.room.enemy and self.pos.roomName != destination.pos.roomName:
                    self.recalc_military_path(self.home.spawn, destination, {
                        "ignore_swamp": True,
                        "use_roads": False,
                    })
                rx, ry = movement.parse_room_to_xy(self.pos.roomName)
                last_updated = stored_data.get_last_updated_tick(self.pos.roomName)
                if not last_updated or Game.time - last_updated > 100:
                    # `-1` in order to undo the adjustment parse_room_to_xy() does for there being both E0S0 and W0N0
                    rrx = (-rx - 1 if rx < 0 else rx) % 10
                    rry = (-ry - 1 if ry < 0 else ry) % 10
                    if (rrx == 4 or rrx == 5 or rrx == 6) and (rry == 4 or rry == 5 or rry == 6) \
                            and not (rrx == 5 and rry == 5):
                        lair_count = 0
                        # should be a source keeper room
                        for lair in self.room.find(FIND_HOSTILE_STRUCTURES):
                            if lair.structureType == STRUCTURE_KEEPER_LAIR:
                                lair_count += 1
                        if lair_count > 0:
                            # recalculate_path_next
                            recalc = True
                            self.memory.rp = self.pos.roomName
                        else:
                            self.log("WARNING: Scout found no lairs in supposed source keeper room {}! Logic error?"
                                     .format(self.pos.roomName))
                    stored_data.update_data(self.room.room)
                self.log("Scouted room {}, {}.".format(rx, ry))

        if self.pos.isEqualTo(destination) or \
                (self.pos.isNearTo(destination)
                 and not movement.is_block_empty(self.room, destination.pos.x, destination.pos.y)):
            if still_exploring:
                destination.memory.travel_time = CREEP_LIFE_TIME - self.creep.ticksToLive
                self.log("Arrived at {} ({}), traveling from {} in {} ticks."
                         .format(destination, destination.pos, self.home.spawn, destination.memory.travel_time))
                destination.memory.explored_at = positions.serialize_pos_xy(destination) + destination.pos.roomName
        elif self.pos.isNearTo(destination):
            self.basic_move_to(destination)
        else:
            self.follow_military_path(self.home.spawn, destination, {
                "ignore_swamp": True,
                "use_roads": False,
            })
            if recalc:
                self.log("Recalculating path due.")
                self.recalc_military_path(self.home.spawn, destination, {
                    "ignore_swamp": True,
                    "use_roads": False
                })
        if self.pos.roomName == destination.pos.roomName and destination.memory.activate_attack_in:
            if len(self.room.defense.dangerous_hostiles()) and _.sum(self.room.defense.dangerous_hostiles(),
                                                                     lambda h: h.owner.username != INVADER_USERNAME
                                                                     and _.sum(h.body, lambda p: p.type == ATTACK
                                                                             or p.type == RANGED_ATTACK
                                                                             or p.type == HEAL)) >= 10:
                rooms_newly_activated = []
                for name in destination.memory.activate_attack_in:
                    activate_attack_in = self.hive.get_room(name)
                    if activate_attack_in:
                        activate_attack_in.defense.activate_live_defenses()
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
        target = self.targets.get_new_target(self, target_single_flag, SCOUT)
        if not target:
            return -1
        path_len = self.get_military_path_length(self.home.spawn, target, {
            "ignore_swamp": True,
            "use_roads": False
        })
        return path_len + 28  # Body size is always 1, so just 25 leeway + 3 here.
