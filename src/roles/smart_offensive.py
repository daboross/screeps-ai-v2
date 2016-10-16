import context
import flags
import role_base
from constants import target_single_flag, PYFIND_HURT_CREEPS
from control import defense
from control import pathdef
from roles.offensive import MilitaryBase
from utilities import movement, hostile_utils
from utilities import volatile_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')

DEF_MOVE_OPTS = {'reusePath': 2, 'ignoreRoads': True, "costCallback": role_base.def_cost_callback}


def kiting_cost_matrix(room_name):
    cache = volatile_cache.mem("kiting_cost_matrix")
    if cache.has(room_name):
        return cache.get(room_name)
    if hostile_utils.enemy_room(room_name):
        return False
    # TODO: some of this is duplicated in pathdef.HoneyTrails

    cost_matrix = __new__(PathFinder.CostMatrix())

    def set_in_range(pos, drange, value, increase_by_center):
        for x in range(pos.x - drange, pos.x + drange + 1):
            for y in range(pos.y - drange, pos.y + drange + 1):
                terrain = Game.map.getTerrainAt(x, y, room_name)
                if terrain != 'wall' and cost_matrix.get(x, y) < value:
                    if terrain == 'swamp':
                        cost_matrix.set(x, y, value + 25)
                    else:
                        cost_matrix.set(x, y, value)
        if increase_by_center > 0 and drange > 0:
            set_in_range(pos, drange - 1, value + increase_by_center, increase_by_center)

    room = context.hive().get_room(room_name)

    if room:
        for struct in room.find(FIND_STRUCTURES):
            if struct.structureType == STRUCTURE_ROAD:
                cost_matrix.set(struct.pos.x, struct.pos.y, 1)
            elif struct.structureType != STRUCTURE_CONTAINER and (struct.structureType != STRUCTURE_RAMPART
                                                                  or not struct.my):
                cost_matrix.set(struct.pos.x, struct.pos.y, 255)
        for creep in room.find(FIND_MY_CREEPS):
            cost_matrix.set(creep.pos.x, creep.pos.y, 255)

    for info in defense.stored_hostiles_in(room_name):
        pos = movement.serialized_pos_to_pos_obj(info.room, info.pos)
        set_in_range(pos, 3, 5, 10)
        cost_matrix.set(pos.x, pos.y, 255)

    for flag in flags.find_flags(room_name, flags.SK_LAIR_SOURCE_NOTED):
        set_in_range(flag.pos, 4, 255, 0)

    for x in [0, 49]:
        for y in range(0, 49):
            terrain = Game.map.getTerrainAt(x, y, room_name)
            if terrain != 'wall':
                existing = cost_matrix.get(x, y)
                if terrain == 'swamp':
                    existing = max(existing, 25)
                cost_matrix.set(x, y, max(existing + 5, 5))
    for y in [0, 49]:
        for x in range(0, 49):
            terrain = Game.map.getTerrainAt(x, y, room_name)
            if terrain != 'wall':
                existing = cost_matrix.get(x, y)
                if terrain == 'swamp':
                    existing = max(existing, 25)
                cost_matrix.set(x, y, max(existing + 5, 5))

    cache.set(room_name, cost_matrix)

    return cost_matrix


def kiting_away_raw_path(origin, targets):
    return PathFinder.search(origin, targets, {
        "roomCallback": kiting_cost_matrix,
        "flee": True,
        "maxRooms": 8,
        "swampCost": 25,
    }).path


class KitingOffense(MilitaryBase):
    def boost(self):
        labs = _(self.home.minerals.labs()).filter(lambda l: l.mineralAmount and l.energy)
        if not len(labs):
            self.memory.boosted = 2
            return False

        if self.memory.boosted == 0:
            lab = labs.find(lambda l: l.mineralType == "XKHO2")
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
            lab = labs.find(lambda l: l.mineralType == "XLHO2")
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
                                self.pos, movement.serialized_pos_to_pos_obj(h.room, h.pos)) <= 3)):
            self.creep.heal(self.creep)

        marker_flag = self.targets.get_new_target(self, target_single_flag, flags.RANGED_DEFENSE)
        if marker_flag is None:
            if self.pos.roomName == self.home.room_name and len(flags.find_flags(self.home, flags.RAID_OVER)):
                self.recycle_me()
                if len(hostiles_nearby) or self.creep.hits < self.creep.hitsMax:
                    self.creep.heal(self.creep)
                return False
            else:
                marker_flag = {'pos': self.find_depot()}

        if len(hostiles_nearby):
            if _.find(hostiles_nearby, 'offensive'):
                hostiles_nearby = _.filter(hostiles_nearby, 'offensive')
            closest = _.min(
                hostiles_nearby,
                lambda h: movement.chebyshev_distance_room_pos(self.pos,
                                                               movement.serialized_pos_to_pos_obj(h.room, h.pos))
            )
            closest_pos = movement.serialized_pos_to_pos_obj(closest.room, closest.pos)
            harmless = not (closest.attack or closest.ranged)
        else:
            enemies = self.room.find(FIND_HOSTILE_CREEPS)
            if len(enemies):
                if self.pos.roomName != marker_flag.pos.roomName:
                    enemies = _.filter(enemies, lambda h: hostile_utils.is_offensive(h)
                                                          and hostile_utils.not_sk(h))
                else:
                    any_offensive = _.find(enemies, hostile_utils.is_offensive)
                    any_nonsk = _.find(enemies, hostile_utils.not_sk)
                    if any_offensive and any_nonsk:
                        enemies = _.filter(enemies, lambda h: hostile_utils.is_offensive(h)
                                                              and hostile_utils.not_sk(h))
                    elif any_offensive:
                        enemies = _.filter(enemies, hostile_utils.is_offensive)
                    elif any_nonsk:
                        enemies = _.filter(enemies, hostile_utils.not_sk)
            if len(enemies):
                closest = _.min(enemies, lambda h: movement.chebyshev_distance_room_pos(self.pos, h.pos))
                closest_pos = closest.pos
                harmless = not (closest.hasActiveBodyparts(ATTACK) or closest.hasActiveBodyparts(RANGED_ATTACK))
            else:
                closest = None
                closest_pos = None
                harmless = False

        if not closest or (closest_pos.roomName != self.pos.roomName
                           and movement.chebyshev_distance_room_pos(closest_pos, self.pos) > 10):
            del self.memory.last_enemy_pos
            # self.creep.say("🐾 💚 🐾", True)
            if self.creep.hits >= self.creep.hitsMax:
                hurt = self.room.find(PYFIND_HURT_CREEPS)
                if len(hurt):
                    damaged = _.max(hurt, lambda p: p.hitsMax - p.hits)
                    if self.pos.isNearTo(damaged):
                        self.creep.heal(damaged)
                    else:
                        self.creep.moveTo(damaged, DEF_MOVE_OPTS)
                    return False
            # TODO: turn this into part of a large generic cross-room movement module
            if not self.pos.isEqualTo(marker_flag.pos):
                distance = movement.chebyshev_distance_room_pos(self.pos, marker_flag.pos)
                if distance > 50:
                    if 'checkpoint' not in self.memory or \
                                    movement.chebyshev_distance_room_pos(self.memory.checkpoint, self.pos) > 50:
                        self.memory.checkpoint = self.pos
                    if hostile_utils.enemy_room(self.memory.checkpoint.roomName):
                        self.memory.checkpoint = self.home.spawn or __new__(RoomPosition(25, 25,
                                                                                         self.home.room_name))

                    self.follow_military_path(_.create(RoomPosition.prototype, self.memory.checkpoint),
                                              marker_flag, {'range': 1})
                    self.creep.say("G1")
                elif distance >= 1:
                    self.creep.moveTo(marker_flag, DEF_MOVE_OPTS)
                    self.creep.say("G2")
                else:
                    self.basic_move_to(marker_flag)
                    self.creep.say("G3")
            return False
        closest_creep = Game.getObjectById(closest.id)
        min_distance = movement.chebyshev_distance_room_pos(closest_pos, self.pos)
        if Game.time % 2:
            self.creep.say("{},{}: {}".format(closest_pos.x, closest_pos.y, min_distance))
        else:
            self.creep.say("🐾 🏹 🐾", True)
        fatigue = (closest_creep and closest_creep.fatigue)
        if not fatigue:
            serialized_enemy_pos = movement.xy_to_serialized_int(closest_pos.x, closest_pos.y)
            if serialized_enemy_pos == self.memory.last_enemy_pos:
                self.memory.enemy_standstill = (self.memory.enemy_standstill or 0) + 1
            else:
                self.memory.last_enemy_pos = serialized_enemy_pos
                del self.memory.enemy_standstill
        standstill = self.memory.enemy_standstill or 0
        if (min_distance <= 4) and self.pos.roomName != closest_pos.roomName:
            self.memory.countdown = (self.memory.countdown or 10) - 1
            if self.memory.countdown <= 0:
                if self.memory.countdown == 0:
                    self.memory.countdown -= 1
                if self.memory.countdown <= 5:
                    del self.memory.countdown
                self.creep.moveTo(marker_flag, DEF_MOVE_OPTS)
        elif not harmless and min_distance <= 3 and _.find(self.pos.lookFor(LOOK_STRUCTURES),
                                                           {'structureType': STRUCTURE_RAMPART, 'my': True}):
            pass
        elif harmless:
            self.creep.moveTo(_.create(RoomPosition.prototype, closest_pos), DEF_MOVE_OPTS)
        elif min_distance < 3 or (min_distance == 3 and not fatigue):
            away_path = None
            try:
                away_path = kiting_away_raw_path(self.pos, [
                    {
                        'pos': _.create(RoomPosition.prototype, movement.serialized_pos_to_pos_obj(h.room, h.pos)),
                        'range': 10,
                    } for h in hostiles_nearby])
                if len(away_path):
                    self.creep.move(pathdef.direction_to(self.pos, away_path[0]))
            except:
                self.log("ERROR calculating/moving by kiting path:\n{}\nPath: {}".format(__except0__.stack,
                                                                                         away_path))
                self.creep.say("ERROR")
                self.go_to_depot()
        elif min_distance > 4 or (min_distance == 4 and (fatigue or standstill > 8)) or harmless:
            self.creep.moveTo(_.create(RoomPosition.prototype, closest_pos), DEF_MOVE_OPTS)

        if closest_pos.roomName == self.pos.roomName and min_distance <= 3:
            closest_creep = Game.getObjectById(closest.id)
            if min_distance == 1:
                self.creep.rangedMassAttack()
            else:
                self.creep.rangedAttack(closest_creep)

    def _calculate_time_to_replace(self):
        marker_flag = self.targets.get_new_target(self, target_single_flag, flags.RANGED_DEFENSE)
        if not marker_flag:
            return -1
        path_len = self.get_military_path_length(self.home.spawn, marker_flag)
        return path_len * 1.05 + _.size(self.creep.body) * 3 + 20
