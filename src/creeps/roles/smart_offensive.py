from typing import Any, Dict, List, Union, cast

from cache import context, volatile_cache
from constants import PYFIND_HURT_CREEPS, RAID_OVER, RANGED_DEFENSE, target_single_flag
from creeps.behaviors.military import MilitaryBase
from empire import stored_data
from jstools import errorlog
from jstools.screeps import *
from position_management import flags
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


def kiting_cost_matrix(room_name, target):
    # type: (str, Flag) -> Union[PathFinder.CostMatrix, bool]
    cache = volatile_cache.mem("kiting_cost_matrix")
    if cache.has(room_name):
        return cache.get(room_name)
    if hostile_utils.enemy_using_room(room_name):
        return False
    # TODO: some of this is duplicated in honey.HoneyTrails

    cost_matrix = __new__(PathFinder.CostMatrix())

    def set_in_range_xy(initial_x, initial_y, distance, value, increase_by_center):
        for x in range(initial_x - distance, initial_x + distance + 1):
            for y in range(initial_y - distance, initial_y + distance + 1):
                if increase_by_center:
                    value_here = value + increase_by_center \
                                         * (distance - movement.chebyshev_distance_xy(initial_x, initial_y, x, y))
                else:
                    value_here = value
                existing_cost = cost_matrix.get(x, y)
                if existing_cost == 0:
                    terrain_here = Game.map.getTerrainAt(x, y, room_name)
                    if terrain_here[0] == 'p':
                        existing_cost = 1
                    elif terrain_here[0] == 's':
                        existing_cost = 25
                    elif terrain_here[0] == 'w':
                        continue
                cost_matrix.set(x, y, existing_cost + value_here)

    def set_in_range(pos, distance, value, increase_by_center):
        pos = pos.pos or pos
        set_in_range_xy(pos.x, pos.y, distance, value, increase_by_center)

    room = context.hive().get_room(room_name)

    if room:
        any_lairs = False
        for struct in cast(List[OwnedStructure], room.find(FIND_STRUCTURES)):
            if struct.structureType == STRUCTURE_ROAD:
                cost_matrix.set(struct.pos.x, struct.pos.y, 1)
            elif struct.structureType != STRUCTURE_CONTAINER and (struct.structureType != STRUCTURE_RAMPART
                                                                  or not struct.my):
                if struct.structureType == STRUCTURE_KEEPER_LAIR:
                    any_lairs = True
                cost_matrix.set(struct.pos.x, struct.pos.y, 255)
        for creep in room.find(FIND_MY_CREEPS):
            cost_matrix.set(creep.pos.x, creep.pos.y, 255)
        if any_lairs:
            for source in room.find(FIND_SOURCES):
                set_in_range(source.pos, 4, 255, 0)
            for mineral in room.find(FIND_MINERALS):
                set_in_range(mineral.pos, 4, 255, 0)
    else:
        data = stored_data.get_data(room_name)
        if data:
            for obstacle in data.obstacles:
                if obstacle.type == StoredObstacleType.ROAD:
                    cost_matrix.set(obstacle.x, obstacle.y, 1)
                elif obstacle.type == StoredObstacleType.SOURCE_KEEPER_LAIR \
                        or obstacle.type == StoredObstacleType.SOURCE_KEEPER_SOURCE \
                        or obstacle.type == StoredObstacleType.SOURCE_KEEPER_MINERAL:
                    set_in_range(obstacle, 4, 255, 0)
                else:
                    cost_matrix.set(obstacle.x, obstacle.y, 255)

    for info in defense.stored_hostiles_in(room_name):
        x, y = positions.deserialize_xy(info.pos)
        set_in_range_xy(x, y, 3, 5, 10)
        cost_matrix.set(x, y, 255)

    for x in [0, 49]:
        for y in range(0, 49):
            existing = cost_matrix.get(x, y)
            if existing == 0:
                terrain = Game.map.getTerrainAt(x, y, room_name)
                if terrain[0] == 'p':
                    existing = 1
                elif terrain[0] == 's':
                    existing = 25
                else:
                    continue  # wall
            cost_matrix.set(x, y, existing + 5)
    for y in [0, 49]:
        for x in range(0, 49):
            existing = cost_matrix.get(x, y)
            if existing == 0:
                terrain = Game.map.getTerrainAt(x, y, room_name)
                if terrain[0] == 'p':
                    existing = 1
                elif terrain[0] == 's':
                    existing = 25
                else:
                    continue  # wall
            cost_matrix.set(x, y, existing + 5)

    cache.set(room_name, cost_matrix)

    return cost_matrix


def kiting_away_raw_path(origin, targets, final_target):
    # type: (RoomPosition,  Union[Dict[str, Any], List[Dict[str, Any]]], Flag) -> List[RoomPosition]
    return PathFinder.search(origin, targets, {
        "roomCallback": lambda room_name: kiting_cost_matrix(room_name, final_target),
        "flee": True,
        "maxRooms": 8,
        "swampCost": 25,
    }).path


_MOVE_TO_OPTIONS = {'reusePath': 2}


class KitingOffense(MilitaryBase):
    def boost(self):
        labs = _.filter(self.home.minerals.labs(), lambda l: l.mineralAmount and l.energy)
        if not len(labs):
            self.memory.boosted = 2
            return False

        if self.memory.boosted == 0:
            lab = _.find(labs, lambda l: l.mineralType == RESOURCE_CATALYZED_KEANIUM_ALKALIDE)
            if lab:
                if self.pos.isNearTo(lab):
                    result = lab.boostCreep(self.creep)
                    if result == OK or result == ERR_NOT_ENOUGH_RESOURCES:
                        self.memory.boosted = 1
                    else:
                        self.log("WARNING: Unknown result from {}.boostCreep({}): {}"
                                 .format(lab, self.creep, result))
                else:
                    self.move_to(lab)
                return True
            else:
                self.memory.boosted = 1

        if self.memory.boosted == 1:
            lab = _.find(labs, lambda l: l.mineralType == RESOURCE_CATALYZED_LEMERGIUM_ALKALIDE)
            if lab:
                if self.pos.isNearTo(lab):
                    result = lab.boostCreep(self.creep)
                    if result == OK or result == ERR_NOT_ENOUGH_RESOURCES:
                        self.memory.boosted = 2
                    else:
                        self.log("WARNING: Unknown result from {}.boostCreep({}): {}"
                                 .format(lab, self.creep, result))
                else:
                    self.move_to(lab)
                return True
            else:
                self.memory.boosted = 2

        return False

    def run(self):
        if self.creep.ticksToLive > 1450 and not (self.memory.boosted >= 2):
            if 'boosted' not in self.memory:
                self.memory.boosted = 0
            if self.boost():
                return False

        hostiles_nearby = defense.stored_hostiles_near(self.pos.roomName)
        if self.creep.hits < self.creep.hitsMax or \
                (len(hostiles_nearby)
                 and _.find(hostiles_nearby,
                            lambda h: movement.chebyshev_distance_room_pos(
                                self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 3)):
            self.creep.heal(self.creep)

        marker_flag = cast(Flag, self.targets.get_new_target(self, target_single_flag, RANGED_DEFENSE))
        if marker_flag is None:
            if self.pos.roomName == self.home.name and len(flags.find_flags(self.home, RAID_OVER)):
                if len(hostiles_nearby) or self.creep.hits < self.creep.hitsMax:
                    self.creep.heal(self.creep)
                return False
            else:
                marker_flag = cast(Flag, {'pos': self.find_depot()})

        if len(hostiles_nearby):
            if _.find(hostiles_nearby, lambda h: h.offensive and movement.chebyshev_distance_room_pos(
                    self.pos, positions.deserialize_xy_to_pos(h.pos, h.room) <= 5)):
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
                if self.pos.roomName != marker_flag.pos.roomName:
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
                harmless = False
                ranged = False
                only_ranged = True
                mass_attack = False

        if not closest or (closest_pos.roomName != self.pos.roomName
                           and movement.chebyshev_distance_room_pos(closest_pos, self.pos) > 10):
            del self.memory.last_enemy_pos
            # self.creep.say("🐾 💚 🐾", True)
            if self.pos.roomName == marker_flag.pos.roomName and self.creep.hits >= self.creep.hitsMax:
                hurt = cast(List[Creep], self.room.find(PYFIND_HURT_CREEPS))
                if len(hurt):
                    damaged = _.min(hurt, lambda p: movement.chebyshev_distance_room_pos(p.pos, self.pos))
                    if self.pos.isNearTo(damaged):
                        self.creep.heal(damaged)
                    else:
                        self.move_to(damaged, _MOVE_TO_OPTIONS)
                    return False
            # TODO: turn this into part of a large generic cross-room movement module
            if not self.pos.isEqualTo(marker_flag.pos):
                distance = movement.chebyshev_distance_room_pos(self.pos, marker_flag.pos)
                if distance > 50:
                    if 'checkpoint' not in self.memory or \
                                    movement.chebyshev_distance_room_pos(self.memory.checkpoint, self.pos) > 50:
                        self.memory.checkpoint = self.pos
                    if self.memory.next_ppos \
                            and movement.chebyshev_distance_room_pos(self.pos, self.memory.next_ppos) > 10 \
                            and not hostile_utils.enemy_owns_room(self.pos.roomName):
                        self.memory.checkpoint = self.pos
                        del self.memory.next_ppos
                        del self.memory.off_path_for
                        del self.memory.lost_path_at
                        del self.memory._move

                    if hostile_utils.enemy_owns_room(self.memory.checkpoint.roomName):
                        self.memory.checkpoint = self.home.spawn or movement.find_an_open_space(self.home.name)

                    self.follow_military_path(_.create(RoomPosition.prototype, self.memory.checkpoint),
                                              marker_flag.pos, {'range': 1})
                    self.creep.say("G1")
                elif distance >= 1:
                    self.move_to(marker_flag, _MOVE_TO_OPTIONS)
                    self.creep.say("G2")
                else:
                    self.basic_move_to(marker_flag)
                    self.creep.say("G3")
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
            return
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
                } for h in hostiles_nearby],
                marker_flag
            )
            if kiting_path is True:
                # errored
                self.creep.say("Err")
                self.go_to_depot()
            elif len(kiting_path):
                self.creep.move(self.pos.getDirectionTo(kiting_path[0]))
            else:
                self.log("WARNING: kiting offense has no path at position {}!".format(self.pos))

    def _calculate_time_to_replace(self):
        marker_flag = self.targets.get_new_target(self, target_single_flag, RANGED_DEFENSE)
        if not marker_flag:
            return -1
        path_len = self.get_military_path_length(self.home.spawn.pos, marker_flag)
        return path_len * 1.05 + _.size(self.creep.body) * CREEP_SPAWN_TIME + 20
