from typing import List, Optional, cast

from constants import INVADER_USERNAME, SCOUT, role_remote_sign, target_single_flag
from creeps.base import RoleBase
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
__pragma__('noalias', 'values')


class Scout(MilitaryBase):
    def run(self):
        destination = cast(Flag, self.targets.get_existing_target(self, target_single_flag))
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
                          or positions.serialize_xy_room_pos(destination.pos) != destination.memory.explored_at

        recalc = False

        if still_exploring:
            # recalculate_path
            if self.memory.rp:
                self.log("Recalculating path due to circumstances in {}.".format(self.memory.rp))
                self.recalc_military_path(self.home.spawn.pos, destination.pos, {
                    "ignore_swamp": True,
                    "use_roads": False,
                })
                del self.memory.rp

            if self.memory.last_room != self.pos.roomName:
                self.memory.last_room = self.pos.roomName
                if self.room.enemy and self.pos.roomName != destination.pos.roomName:
                    self.recalc_military_path(self.home.spawn.pos, destination.pos, {
                        "ignore_swamp": True,
                        "use_roads": False,
                    })
                last_updated = stored_data.get_last_updated_tick(self.pos.roomName)
                if not last_updated or Game.time - last_updated > 100:
                    if movement.is_room_inner_circle_of_sector(self.pos.roomName):
                        lair_count = 0
                        # should be a source keeper room
                        for lair in cast(List[Structure], self.room.find(FIND_HOSTILE_STRUCTURES)):
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
                self.log("scouted room: {}".format(self.pos.roomName))

        if self.pos.isEqualTo(destination) or \
                (self.pos.isNearTo(destination)
                 and not movement.is_block_empty(self.room, destination.pos.x, destination.pos.y)):
            if still_exploring:
                destination.memory.travel_time = CREEP_LIFE_TIME - self.creep.ticksToLive
                self.log("Arrived at {} ({}), traveling from {} in {} ticks."
                         .format(destination, destination.pos, self.home.spawn, destination.memory.travel_time))
                destination.memory.explored_at = positions.serialize_xy_room_pos(destination.pos)
        elif self.pos.isNearTo(destination):
            self.basic_move_to(destination)
        else:
            self.follow_military_path(self.home.spawn.pos, destination.pos, {
                "ignore_swamp": True,
                "use_roads": False,
            })
            if recalc:
                self.log("Recalculating path due.")
                self.recalc_military_path(self.home.spawn.pos, destination.pos, {
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
                    print(message)
                    Game.notify(message)

    def _calculate_time_to_replace(self):
        target = cast(Flag, self.targets.get_new_target(self, target_single_flag, SCOUT))
        if not target:
            return -1
        path_len = self.get_military_path_length(self.home.spawn.pos, target.pos, {
            "ignore_swamp": True,
            "use_roads": False
        })
        return path_len + 28  # Body size is always 1, so just 25 leeway + 3 here.


class Rndrs(RoleBase):
    def run(self):
        if self.pos.isNearTo(self.room.room.controller):
            self.creep.signController(self.room.room.controller, self.room.get_message())
            if self.memory.role == role_remote_sign:
                self.creep.suicide()
            else:
                self.memory.role = role_remote_sign
        else:
            self.move_to(self.room.room.controller)


class RndrsRemote(RoleBase):
    def find_new_target(self):
        # type: () -> Optional[str]
        all_possibilities = []
        for flag in self.home.mining.active_mines:
            room = Game.rooms[flag.pos.roomName]
            if room and room.controller:
                if not room.controller.sign:
                    all_possibilities.append(flag.pos.roomName)
                else:
                    room_mind = self.hive.get_room(flag.pos.roomName)
                    message = room_mind.get_message()
                    if message != room.controller.sign.text:
                        all_possibilities.append(flag.pos.roomName)
        if not len(all_possibilities):
            return None
        target_remote_name = _.sample(all_possibilities)
        self.memory.target_remote = target_remote_name
        return target_remote_name

    def run(self):
        target_remote_name = self.memory.target_remote
        if not target_remote_name:
            target_remote_name = self.find_new_target()
            if not target_remote_name:
                self.creep.suicide()
                return

        target_remote = Game.rooms[target_remote_name]
        if not target_remote:
            target_remote_name = self.find_new_target()
            if not target_remote_name:
                self.creep.suicide()
                return
            target_remote = Game.rooms[target_remote_name]

        if self.pos.isNearTo(target_remote.controller):
            self.creep.signController(target_remote.controller, self.room.get_message())
            target_remote_name = self.find_new_target()
            if not target_remote_name:
                self.creep.suicide()
        else:
            self.move_to(target_remote.controller)
