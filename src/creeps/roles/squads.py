from typing import List, Optional, cast

from cache import volatile_cache
from constants import role_recycling, target_single_flag
from creeps.base import RoleBase
from creeps.behaviors.military import MilitaryBase
from creeps.roles.smart_offensive import kiting_away_raw_path
from jstools import errorlog
from jstools.screeps import *
from position_management.locations import Location
from rooms import defense
from utilities import hostile_utils, movement, positions

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


class SquadInit(RoleBase):
    def run(self):
        target = cast(Flag, self.target(target_single_flag))
        if not target:
            self.log("Squad init has no target! D:")
            self.memory.last_role = self.memory.role
            self.memory.role = role_recycling
            return

        self.home.squads.note_stage0_creep(self, target)
        self.home.squads.renew_or_depot(self)

    def go_to_depot(self):
        if self.findSpecialty() == ATTACK:
            target = self.room.find_closest_by_range(FIND_HOSTILE_CREEPS, self.pos)
            if target:
                self.move_to(target)
                return

        RoleBase.go_to_depot(self)

    def get_replacement_time(self):
        return Game.time + CREEP_LIFE_TIME * 2


class SquadFinalRenew(RoleBase):
    def run(self):
        self.home.squads.renew_or_depot(self)
        self.home.squads.note_stage1_creep(self, self.memory.squad)

    def go_to_depot(self):
        if self.findSpecialty() == ATTACK:
            target = cast(Optional[Creep], self.room.find_closest_by_range(FIND_HOSTILE_CREEPS, self.pos))
            if target:
                self.move_to(target)
                self.creep.attack(target)
                return

        RoleBase.go_to_depot(self)

    def get_replacement_time(self):
        return Game.time + CREEP_LIFE_TIME * 2


class SquadFinalBoost(RoleBase):
    def run(self):
        self.home.squads.boost_or_depot(self)
        self.home.squads.note_stage2_creep(self, self.memory.squad)

    def go_to_depot(self):
        if self.findSpecialty() == ATTACK:
            target = cast(Optional[Creep], self.room.find_closest_by_range(FIND_HOSTILE_CREEPS, self.pos))
            if target:
                self.move_to(target)
                self.creep.attack(target)
                return

        RoleBase.go_to_depot(self)


class SquadDrone(MilitaryBase):
    def run(self):
        self.home.squads.note_stage3_creep(self, self.memory.squad)

    def run_squad(self, members, target):
        # type: (List[SquadDrone], Location) -> Optional[bool]
        pass

    def find_target_here(self, target):
        # type: (Location) -> Optional[RoomPosition]
        return None

    def get_replacement_time(self):
        return Game.time + CREEP_LIFE_TIME * 2


class SquadHeal(SquadDrone):
    def run_squad(self, members, target):
        # type: (List[SquadDrone], Location) -> None
        best_near_rank = -Infinity
        best_near = None
        best_damaged_rank = -Infinity
        best_damaged_near = None
        for to_check in members:
            if self.pos.isNearTo(to_check.pos):
                specialty = to_check.findSpecialty()
                if specialty == HEAL and to_check.creep.hits < to_check.creep.hitsMax * 0.7:
                    rank = 7
                elif specialty == RANGED_ATTACK or specialty == ATTACK or specialty == WORK:
                    rank = 5
                else:
                    rank = 1
                if to_check.creep.hits < to_check.creep.hitsMax:
                    rank += (to_check.creep.hitsMax - to_check.creep.hits) / to_check.creep.hitsMax
                    if best_damaged_rank < rank:
                        best_damaged_near = to_check
                        best_damaged_rank = rank
                if best_near_rank < rank:
                    best_near = to_check
                    best_near_rank = rank
        if best_damaged_near:
            result = self.creep.heal(best_damaged_near.creep)
            if result != OK:
                self.log("Unknown result using {}.heal({}): {}"
                         .format(self.creep, best_damaged_rank.creep, result))
        elif movement.chebyshev_distance_room_pos(self.pos, target) < 100 and best_near:
            result = self.creep.heal(best_near.creep)
            if result != OK:
                self.log("Unknown result using {}.heal({}): {}"
                         .format(self.creep, best_near.creep, result))

    def findSpecialty(self):
        return HEAL


class SquadTowerDrainHeal(SquadDrone):
    def run_squad(self, members, target):
        # type: (List[SquadDrone], Location) -> None
        best_near_rank = -Infinity
        best_near = None
        best_damaged_rank = -Infinity
        best_damaged_near = None
        most_damage = 0
        most_damaged = None
        for to_check in members:
            damage = (to_check.creep.hitsMax - to_check.creep.hits) / to_check.creep.hitsMax
            if self.pos.isNearTo(to_check.pos):
                specialty = to_check.findSpecialty()
                if specialty == HEAL and to_check.creep.hits < to_check.creep.hitsMax * 0.7:
                    rank = 7
                elif specialty == RANGED_ATTACK or specialty == ATTACK or specialty == WORK:
                    rank = 5
                else:
                    rank = 1
                if damage:
                    rank += damage
                    if best_damaged_rank < rank:
                        best_damaged_near = to_check
                        best_damaged_rank = rank
                if best_near_rank < rank:
                    best_near = to_check
                    best_near_rank = rank
            if damage > most_damage:
                most_damage = damage
                most_damaged = to_check
        if best_damaged_near:
            result = self.creep.heal(best_damaged_near.creep)
            if result != OK:
                self.log("Unknown result using {}.heal({}): {}"
                         .format(self.creep, best_damaged_rank.creep, result))
        elif best_near:
            result = self.creep.heal(best_near.creep)
            if result != OK:
                self.log("Unknown result using {}.heal({}): {}"
                         .format(self.creep, best_near.creep, result))
        elif most_damaged:
            result = self.creep.rangedHeal(most_damaged.creep)
            if result != OK:
                self.log("Unknown result using {}.rangedHeal({}): {}"
                         .format(self.creep, most_damaged.creep, result))
        if not self.creep.__moved and most_damaged and not self.pos.isNearTo(most_damaged.pos):
            self.move_to(most_damaged)

    def findSpecialty(self):
        return HEAL


class SquadRangedAttack(SquadDrone):
    def run_squad(self, members, target):
        # type: (List[SquadDrone], Location) -> None
        attacked = False
        here = cast(List[Creep], self.room.find(FIND_HOSTILE_CREEPS))
        if len(here):
            directly_nearby = 0
            best = None
            best_range = Infinity
            best_rank = -Infinity
            for enemy in here:
                enemy_range = movement.chebyshev_distance_room_pos(enemy.pos, self.pos)
                if enemy_range <= 3:
                    specialty = enemy.findSpecialty()
                    if specialty == ATTACK or specialty == RANGED_ATTACK:
                        rank = 40
                    elif specialty == WORK:
                        rank = 35
                    else:
                        rank = 30
                    if _.some(self.room.look_at(LOOK_STRUCTURES, enemy.pos),
                              lambda s: s.structureType == STRUCTURE_RAMPART and not s.my):
                        rank -= 20
                    rank += (enemy.hitsMax - enemy.hits) / enemy.hitsMax * 5
                    if enemy_range < 1:
                        directly_nearby += rank
                    if rank > best_rank:
                        best_rank = rank
                        best_range = enemy_range
                        best = enemy
            if directly_nearby > 65 or best_range <= 1:
                result = self.creep.rangedMassAttack()
                if result != OK:
                    self.log("Unknown result from {}.rangedMassAttack(): {}"
                             .format(self.creep, result))
                attacked = True
            elif best:
                result = self.creep.rangedAttack(best)
                if result != OK:
                    self.log("Unknown result from {}.rangedAttack({}): {}"
                             .format(self.creep, best, result))
                attacked = True
        if not attacked:
            to_dismantle = volatile_cache.mem('dismantle_squad_dismantling').get(target.name)
            if to_dismantle:
                self.creep.rangedAttack(to_dismantle)

    def findSpecialty(self):
        return RANGED_ATTACK


class SquadAllAttack(SquadDrone):
    def run_squad(self, members, target):
        # type: (List[SquadDrone], Location) -> None
        if _.all(members, lambda x: x.pos.roomName == target.roomName):
            enemy = self.room.find_closest_by_range(FIND_HOSTILE_CREEPS, self.pos)
            self.move_to(enemy)
            self.creep.attack(cast(Creep, enemy))

    def findSpecialty(self):
        return ATTACK


_MOVE_TO_OPTIONS = {'reusePath': 1, 'useRoads': False}

# this is hardcoded in the screeps engine
# https://github.com/screeps/engine/blob/1a7175be293240aafa93e514c0487a82e5a383d8/src/processor/intents/creeps/rangedMassAttack.js#L30
#  var distanceRate = {1: 1, 2: 0.4, 3: 0.1};
ranged_mass_attack_rates = [1, 1, 0.4, 0.1]  # array for fast indexing


class SquadKitingRangedAttack(SquadDrone):
    def run_squad(self, members, target, do_things = False):
        # type: (List[SquadDrone], Location, bool) -> bool
        hostiles_nearby = defense.stored_hostiles_near(self.pos.roomName)
        if self.creep.hits < self.creep.hitsMax or \
                (len(hostiles_nearby)
                 and _.find(hostiles_nearby,
                            lambda h: movement.chebyshev_distance_room_pos(
                                self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 3)):
            self.creep.heal(self.creep)

        marker_flag = target

        if len(hostiles_nearby):
            if _.find(hostiles_nearby, lambda h: h.offensive and movement.chebyshev_distance_room_pos(
                    self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 5):
                hostiles_nearby = _.filter(hostiles_nearby, 'offensive')
            nearby = _.filter(hostiles_nearby,
                              lambda h: movement.chebyshev_distance_room_pos(
                                  self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 5)
            closest = _.min(
                hostiles_nearby,
                lambda h: movement.chebyshev_distance_room_pos(self.pos, positions.deserialize_xy_to_pos(h.pos, h.room))
                          - (5 if h.offensive else 0)
            )
            closest_pos = positions.deserialize_xy_to_pos(closest.pos, closest.room)
            harmless = not _.some(nearby, lambda x: x.attack or x.ranged)
            ranged = _.some(nearby, lambda x: x.ranged)
            only_ranged = not _.some(nearby,
                                     lambda h: movement.chebyshev_distance_room_pos(
                                         self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 4 and h.attack)
            mass_attack = _.some(nearby, lambda h: movement.chebyshev_distance_room_pos(
                self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 1
                                                   and h.room == self.pos.roomName)
        else:
            enemies = self.room.find(FIND_HOSTILE_CREEPS)
            if len(enemies):
                if self.pos.roomName != marker_flag.roomName:
                    enemies = _.filter(enemies, lambda h: hostile_utils.is_offensive(h)
                                                          and hostile_utils.not_sk(h))
                else:
                    any_offensive = _.find(enemies, hostile_utils.is_offensive)
                    if any_offensive:
                        enemies = _.filter(enemies, lambda h: hostile_utils.is_offensive(h)
                                                              and hostile_utils.not_sk(h))
                    else:
                        enemies = _.filter(enemies, hostile_utils.not_sk)
            if len(enemies):
                closest = _.min(enemies, lambda h: movement.chebyshev_distance_room_pos(self.pos, h.pos))
                closest_pos = closest.pos
                nearby = _.filter(enemies, lambda h: movement.chebyshev_distance_room_pos(h.pos, self.pos) <= 5)
                harmless = not _.some(nearby,
                                      lambda h: h.hasActiveBodyparts(ATTACK) or h.hasActiveBodyparts(RANGED_ATTACK)) \
                           and self.creep.hits >= self.creep.hitsMax
                ranged = _.some(nearby, lambda h: h.hasActiveBodyparts(RANGED_ATTACK))
                only_ranged = not _.some(nearby,
                                         lambda h:
                                         movement.chebyshev_distance_room_pos(self.pos, h.pos) <= 4
                                         and h.hasBodyparts(ATTACK))
                mass_attack = _.some(nearby, lambda h: self.pos.isNearTo(h.pos) and self.pos.roomName == h.pos.roomName)
            else:
                closest = None
                closest_pos = None
                nearby = []
                harmless = False
                ranged = False
                only_ranged = True
                mass_attack = False
        if not closest:
            if not do_things:
                return False
            self.move_to(target)
            return False
        closest_creep = cast(Creep, Game.getObjectById(closest.id))
        min_distance = movement.chebyshev_distance_room_pos(closest_pos, self.pos)
        if Game.time % 2:
            self.creep.say("{},{}: {}".format(closest_pos.x, closest_pos.y, min_distance))
        else:
            self.creep.say("🐾 🏹 🐾", True)
        fatigue = (closest_creep and (closest_creep.fatigue or not closest_creep.hasActiveBodyparts(MOVE)))
        if self.memory.healing:
            self.memory.healing = self_damaged = self.creep.hits < self.creep.hitsMax
        else:
            # If 1/4 of our ranged attack parts are dead.
            total_ra = self.creep.getBodyparts(RANGED_ATTACK)
            alive_ra = self.creep.getActiveBodyparts(RANGED_ATTACK)
            self.memory.healing = self_damaged = (total_ra < 10 and alive_ra < total_ra / 2) or alive_ra < total_ra / 3

        if closest_pos.roomName == self.pos.roomName and min_distance <= 3:
            if mass_attack:
                self.creep.rangedMassAttack()
            else:
                self.creep.rangedAttack(closest_creep)

        if (min_distance <= 6) and self.pos.roomName != closest_pos.roomName:
            self.memory.countdown = (self.memory.countdown or 10) - 1
            if self.memory.countdown <= 0:
                if self.memory.countdown == 0:
                    self.memory.countdown -= 1
                if self.memory.countdown <= 5:
                    del self.memory.countdown
                self.move_to(marker_flag, _MOVE_TO_OPTIONS)
            return False
        if ranged and self_damaged:
            safe_distance = 5
        elif ranged and only_ranged:
            safe_distance = 0
        else:
            safe_distance = 3
        should_run = (not _.some(self.pos.lookFor(LOOK_STRUCTURES), {'structureType': STRUCTURE_RAMPART, 'my': True})
                      and not harmless
                      and (min_distance < safe_distance or (min_distance == safe_distance and not fatigue)))

        should_approach = not should_run and (harmless or min_distance > safe_distance)
        if should_approach:
            moved = False
            if min_distance == 1 and len(nearby) > 1:
                # NOTE: expensive!!
                def rate_attack_pos(x, y):
                    summation = 0
                    for enemy in nearby:
                        if enemy.pos.x:
                            ex = enemy.pos.x
                            ey = enemy.pos.y
                        else:
                            ex, ey = positions.deserialize_xy(enemy.pos)
                        distance = movement.chebyshev_distance_xy(x, y, ex, ey)
                        summation += ranged_mass_attack_rates[distance] or 0
                    return summation * 10 + movement.chebyshev_distance_xy(x, y, self.pos.x, self.pos.y)

                best_attack_x = self.pos.x
                best_attack_y = self.pos.y
                best_attack_rate = rate_attack_pos(best_attack_x, best_attack_y)
                for xx in range(self.pos.x - 1, self.pos.x + 1):
                    for yy in range(self.pos.y - 1, self.pos.y + 1):
                        rate = rate_attack_pos(xx, yy)
                        if rate > best_attack_rate:
                            best_attack_x = xx
                            best_attack_y = yy
                            best_attack_rate = rate
                if best_attack_x != self.pos.x or best_attack_y != self.pos.y:
                    self.move_to(__new__(RoomPosition(best_attack_x, best_attack_y, self.pos.roomName)))
                    moved = True
            if not moved:
                # NOTE: this depends on our custom moveTo function not checking for instanceof RoomPosition
                self.move_to(closest_pos, _MOVE_TO_OPTIONS)
        elif should_run:
            kiting_path = errorlog.try_exec(
                'kiting-offense',
                kiting_away_raw_path,
                lambda pos: "Error calculating or moving by kiting path at pos {}.".format(pos),
                self.pos,
                [{
                    'pos': positions.deserialize_xy_to_pos(h.pos, h.room),
                    'range': 10,
                } for h in hostiles_nearby], marker_flag
            )
            if kiting_path is True:
                # errored
                self.creep.say("Err")
                self.go_to_depot()
            elif len(kiting_path):
                self.creep.move(self.pos.getDirectionTo(kiting_path[0]))
            else:
                self.log("WARNING: kiting offense has no path at position {}!".format(self.pos))
        return True

    def findSpecialty(self):
        return RANGED_ATTACK


class SquadKitingAttack(SquadDrone):
    def run_squad(self, members, target, do_things = False):
        """
        :type members: list[SquadDrone]
        :type target: position_management.locations.Location
        :type do_things: bool
        """
        if not do_things:
            return
        hostiles_nearby = defense.stored_hostiles_near(self.pos.roomName)
        if self.creep.hits < self.creep.hitsMax or \
                (len(hostiles_nearby)
                 and _.find(hostiles_nearby,
                            lambda h: movement.chebyshev_distance_room_pos(
                                self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 3)):
            self.creep.heal(self.creep)

        marker_flag = target

        if len(hostiles_nearby):
            if _.find(hostiles_nearby, lambda h: h.offensive and movement.chebyshev_distance_room_pos(
                    self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 5):
                hostiles_nearby = _.filter(hostiles_nearby, 'offensive')
            nearby = _.filter(hostiles_nearby,
                              lambda h: movement.chebyshev_distance_room_pos(
                                  self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 5)
            closest = _.min(
                hostiles_nearby,
                lambda h: movement.chebyshev_distance_room_pos(self.pos, positions.deserialize_xy_to_pos(h.pos, h.room))
                          - (5 if h.offensive else 0)
            )
            closest_pos = positions.deserialize_xy_to_pos(closest.pos, closest.room)
            harmless = not _.some(nearby, lambda x: x.attack or x.ranged)
            ranged = _.some(nearby, lambda x: x.ranged)
            only_ranged = not _.some(nearby,
                                     lambda h: movement.chebyshev_distance_room_pos(
                                         self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 4 and h.attack)
            mass_attack = _.some(nearby, lambda h: movement.chebyshev_distance_room_pos(
                self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 1
                                                   and h.room == self.pos.roomName)
        else:
            enemies = self.room.find(FIND_HOSTILE_CREEPS)
            if len(enemies):
                if self.pos.roomName != marker_flag.roomName:
                    enemies = _.filter(enemies, lambda h: hostile_utils.is_offensive(h)
                                                          and hostile_utils.not_sk(h))
                else:
                    any_offensive = _.find(enemies, hostile_utils.is_offensive)
                    if any_offensive:
                        enemies = _.filter(enemies, lambda h: hostile_utils.is_offensive(h)
                                                              and hostile_utils.not_sk(h))
                    else:
                        enemies = _.filter(enemies, hostile_utils.not_sk)
            if len(enemies):
                closest = _.min(enemies, lambda h: movement.chebyshev_distance_room_pos(self.pos, h.pos))
                closest_pos = closest.pos
                nearby = _.filter(enemies, lambda h: movement.chebyshev_distance_room_pos(h.pos, self.pos) <= 5)
                harmless = not _.some(nearby,
                                      lambda h: h.hasActiveBodyparts(ATTACK) or h.hasActiveBodyparts(RANGED_ATTACK)) \
                           and self.creep.hits >= self.creep.hitsMax
                ranged = _.some(nearby, lambda h: h.hasActiveBodyparts(RANGED_ATTACK))
                only_ranged = not _.some(nearby,
                                         lambda h:
                                         movement.chebyshev_distance_room_pos(self.pos, h.pos) <= 4
                                         and h.hasBodyparts(ATTACK))
                mass_attack = _.some(nearby, lambda h: self.pos.isNearTo(h.pos) and self.pos.roomName == h.pos.roomName)
            else:
                closest = None
                closest_pos = None
                nearby = []
                harmless = False
                ranged = False
                only_ranged = True
                mass_attack = False
        if not closest:
            self.move_to(target)
            return
        closest_creep = cast(Creep, Game.getObjectById(closest.id))
        min_distance = movement.chebyshev_distance_room_pos(closest_pos, self.pos)
        if Game.time % 2:
            self.creep.say("{},{}: {}".format(closest_pos.x, closest_pos.y, min_distance))
        else:
            self.creep.say("🏹", True)
        fatigue = (closest_creep and (closest_creep.fatigue or not closest_creep.hasActiveBodyparts(MOVE)))
        if self.memory.healing:
            self.memory.healing = self_damaged = self.creep.hits < self.creep.hitsMax
        else:
            # If 1/4 of our ranged attack parts are dead.
            total_ra = self.creep.getBodyparts(ATTACK)
            alive_ra = self.creep.getActiveBodyparts(ATTACK)
            self.memory.healing = self_damaged = (total_ra < 10 and alive_ra < total_ra / 2) or alive_ra < total_ra / 3

        if closest_pos.roomName == self.pos.roomName and min_distance <= 1:
            self.creep.attack(closest_creep)

        if (min_distance <= 6) and self.pos.roomName != closest_pos.roomName:
            self.memory.countdown = (self.memory.countdown or 10) - 1
            if self.memory.countdown <= 0:
                if self.memory.countdown == 0:
                    self.memory.countdown -= 1
                if self.memory.countdown <= 5:
                    del self.memory.countdown
                self.move_to(marker_flag, _MOVE_TO_OPTIONS)
            return
        if ranged and self_damaged:
            safe_distance = 5
        elif ranged and only_ranged:
            safe_distance = 0
        elif self_damaged:
            safe_distance = 3
        else:
            safe_distance = 0
        should_run = (not _.some(self.pos.lookFor(LOOK_STRUCTURES), {'structureType': STRUCTURE_RAMPART, 'my': True})
                      and not harmless
                      and (min_distance < safe_distance or (min_distance == safe_distance and not fatigue)))

        should_approach = not should_run and (harmless or min_distance > safe_distance)
        if should_approach:
            # NOTE: this depends on our custom moveTo function not checking for instanceof RoomPosition
            self.move_to(closest_pos, _MOVE_TO_OPTIONS)
        elif should_run:
            kiting_path = errorlog.try_exec(
                'kiting-offense',
                kiting_away_raw_path,
                lambda pos: "Error calculating or moving by kiting path at pos {}.".format(pos),
                self.pos,
                [{
                    'pos': positions.deserialize_xy_to_pos(h.pos, h.room),
                    'range': 10,
                } for h in hostiles_nearby], marker_flag
            )
            if kiting_path is True:
                # errored
                self.creep.say("Err")
                self.go_to_depot()
            elif len(kiting_path):
                self.creep.move(self.pos.getDirectionTo(kiting_path[0]))
            else:
                self.log("WARNING: kiting offense has no path at position {}!".format(self.pos))

    def findSpecialty(self):
        return RANGED_ATTACK


class SquadDirectSupportHeal(SquadDrone):
    def run_squad(self, members, target):
        # type: (List[SquadDrone], Location) -> None
        best_near_rank = -Infinity
        best_near = None
        best_damaged_rank = -Infinity
        best_damaged_near = None
        most_damage = 0
        most_damaged = None
        for to_check in members:
            damage = (to_check.creep.hitsMax - to_check.creep.hits) / to_check.creep.hitsMax
            if self.pos.isNearTo(to_check.pos):
                specialty = to_check.findSpecialty()
                if specialty == HEAL and to_check.creep.hits < to_check.creep.hitsMax * 0.7:
                    rank = 7
                elif specialty == RANGED_ATTACK or specialty == ATTACK or specialty == WORK:
                    rank = 5
                else:
                    rank = 1
                if damage:
                    rank += damage
                    if best_damaged_rank < rank:
                        best_damaged_near = to_check
                        best_damaged_rank = rank
                if best_near_rank < rank:
                    best_near = to_check
                    best_near_rank = rank
            if damage > most_damage:
                most_damage = damage
                most_damaged = to_check
        if best_damaged_near:
            result = self.creep.heal(best_damaged_near.creep)
            if result != OK:
                self.log("Unknown result using {}.heal({}): {}"
                         .format(self.creep, best_damaged_rank.creep, result))
        elif best_near:
            result = self.creep.heal(best_near.creep)
            if result != OK:
                self.log("Unknown result using {}.heal({}): {}"
                         .format(self.creep, best_near.creep, result))
        elif most_damaged:
            result = self.creep.rangedHeal(most_damaged.creep)
            if result != OK:
                self.log("Unknown result using {}.rangedHeal({}): {}"
                         .format(self.creep, most_damaged.creep, result))
        if not self.creep.__moved:
            if most_damaged and not self.pos.isNearTo(most_damaged.pos):
                self.move_to(most_damaged)

    def findSpecialty(self):
        return HEAL
