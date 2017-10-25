from typing import List, TYPE_CHECKING, cast

from constants import KILLER_CLAIM, role_recycling, \
    target_single_flag
from creeps.behaviors.military import MilitaryBase
from empire import stored_data
from jstools.screeps import *
from utilities import movement

if TYPE_CHECKING:
    pass

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


def is_structure_to_remove(structure: Structure) -> bool:
    return structure.structureType != STRUCTURE_ROAD and structure.structureType != STRUCTURE_CONTROLLER


class KillerClaim(MilitaryBase):
    def run(self):
        claim_flag = cast(Flag, self.targets.get_new_target(self, target_single_flag, KILLER_CLAIM))
        if not claim_flag:
            self.log("ok - no more targets, recycling.")
            self.memory.last_role = self.memory.role
            self.memory.role = role_recycling
            return
        if self.creep.ticksToLive < 2:
            self.log("ok - almost dead before reaching {}.", claim_flag.pos.roomName)
        if self.pos.roomName != claim_flag.pos.roomName:
            target = claim_flag.pos
            if 'checkpoint' not in self.memory or \
                            movement.chebyshev_distance_room_pos(self.memory.checkpoint, self.pos) > 50:
                self.memory.checkpoint = self.pos

            opts = {'range': 15, 'use_roads': False}
            if self.creep.getActiveBodyparts(MOVE) >= len(self.creep.body) * 5 / 7:
                opts.ignore_swamp = True
                opts.use_roads = False
            elif self.creep.getActiveBodyparts(MOVE) >= len(self.creep.body) / 2:
                opts.use_roads = False
            self.follow_military_path(_.create(RoomPosition.prototype, self.memory.checkpoint), target, opts)
            return False

        target = self.creep.room.controller
        if not target:
            self.log("ERROR: Cleaner can't find controller in room {}!".format(self.creep.room.name))
            self.targets.untarget_all(self)
            return True

        if not self.pos.isNearTo(target):
            self.move_to(target)
            return False

        structures = cast(List[Structure], self.room.find(FIND_STRUCTURES))
        any_structures = _.any(structures, is_structure_to_remove)

        construction_sites = cast(List[ConstructionSite], self.room.find(FIND_CONSTRUCTION_SITES))
        any_sites = len(construction_sites)

        if target.my:
            something_mine = _.find(structures, lambda s: s.my and is_structure_to_remove(s))
            if something_mine:
                self.log("WARNING: cleaning creep found an owned {} in room {}"
                         " we just freshly claimed to clean up! Advise!"
                         .format(something_mine.structureType, self.pos.roomName))
            else:
                if any_structures:
                    self.log("ok - removing all structures in {}"
                             .format(self.pos.roomName))
                    for structure in structures:
                        if is_structure_to_remove(structure):
                            result = structure.destroy()
                            if result != OK:
                                self.log("error destroying structure {} (pos: {}, room: {}, room.controller: {},"
                                         " room.controller.my: {}, owner: {}, owner.username: {}): {}",
                                         structure, structure.pos, structure.room, structure.room.controller,
                                         structure.room.controller.my, cast(OwnedStructure, structure).owner,
                                         cast(OwnedStructure, structure).owner.username
                                         if cast(OwnedStructure, structure).owner else 'null',
                                         result)
                if any_sites:
                    self.log("ok - removing all construction sites in {}"
                             .format(self.pos.roomName))
                    for site in construction_sites:
                        result = site.remove()
                        if result != OK:
                            self.log("error removing site {}: {}", site, result)
                if not any_structures and not any_sites:
                    self.log("ok - room {} cleaned. un-claiming."
                             .format(self.pos.roomName))
                    target.unclaim()
            return
        elif not target.my and not any_structures and not any_sites:
            self.log("ok - room {} clean. refreshing data, removing memory and removing target"
                     " (controller: {}, owned: {})"
                     .format(self.pos.roomName, target, target.my))
            stored_data.update_data(self.creep.room)
            claim_flag.remove()
            del Memory.rooms[self.pos.roomName]
            self.targets.untarget_all(self)
            return

        if target.owner:
            self.creep.attackController(target)
        else:
            self.creep.room.memory.pause = True  # ensure a room doesn't run if we accidentally had a structure in it...
            self.log("ok - room {} found. claiming."
                     .format(self.pos.roomName))
            self.creep.claimController(target)
            self.creep.signController(target, '')

    def _calculate_time_to_replace(self):
        if self.creep.getActiveBodyparts(CLAIM) > 1:
            target = self.targets.get_new_target(self, target_single_flag, KILLER_CLAIM)
            if not target:
                return -1
            path_len = self.get_military_path_length(self.home.spawn.pos, target.pos)
            return path_len + _.size(self.creep.body) * CREEP_SPAWN_TIME
        else:
            return 0
