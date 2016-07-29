from math import floor

import context
import creep_utils
from base import *
from constants import creep_base_big_harvester, creep_base_worker

__pragma__('noalias', 'name')


def run(spawn):
    if not Memory.meta.no_more_spawning and not spawn.spawning:
        # TODO: extra roles which might need >1000 energy!
        max = min(spawn.room.energyCapacityAvailable, 1250)
        spawn_with_energy(spawn, max)


def spawn_with_energy(spawn, energy):
    # If we have very few harvesters, try to spawn a new one! But don't make it too small, if we already have a big harvester.
    # 150 * work_mass will make a new harvester somewhat smaller than the existing one, but it shouldn't be too bad.
    # We *can* assume that all work_mass at this point is in harvesters, since creep_utils.reassign_roles() will reassign
    # everyone to harvester if there are fewer than 2 harvesters existing.
    if creep_utils.role_count("harvester") < 2 \
            and spawn.room.energyAvailable >= 150 * context.room().work_mass:
        energy = spawn.room.energyAvailable

    if spawn.room.energyAvailable >= energy:
        base, role = creep_utils.get_role_name()

        if not role:
            Memory.meta.no_more_spawning = True
            return

        if base is creep_base_big_harvester:
            if energy < 550:
                if energy % 100 == 0:
                    parts = [MOVE, MOVE]
                    energyUsed = 100
                    while energyUsed <= energy - 100:
                        parts.append(WORK)
                        energyUsed += 100
                    spawn_with_array(spawn, role, base, parts)
                else:
                    parts = [MOVE]
                    energyUsed = 50
                    while energyUsed <= energy - 100:
                        parts.append(WORK)
                        energyUsed += 100
                    spawn_with_array(spawn, role, base, parts)
            else:
                parts = [WORK, WORK, WORK, WORK, WORK, MOVE, MOVE]
                spawn_with_array(spawn, role, base, parts)
        elif base is creep_base_worker:
            if energy >= 500:
                parts = []
                part_idea = [MOVE, MOVE, CARRY, WORK]
                num_sections = int(floor(energy / 250))
                for i in range(0, num_sections):
                    for part in part_idea:
                        parts.append(part)
                spawn_with_array(spawn, role, base, parts)
            elif energy >= 400:
                spawn_with_array(spawn, role, base, [
                    MOVE, MOVE, MOVE, CARRY, WORK, WORK
                ])
            elif energy >= 250:
                spawn_with_array(spawn, role, base, [MOVE, MOVE, CARRY, WORK])
            elif energy >= 200:
                spawn_with_array(spawn, role, base, [MOVE, CARRY, WORK])
        else:
            print("[spawning] Unknown creep base {}!".format(base))


def spawn_with_array(spawn, role, base, parts):
    name = random_four_digits()
    print("[spawning] Choosing role {} with parts {}".format(role, parts))
    result = spawn.createCreep(parts, name, {"role": role, "base": base})
    if result != OK and not Game.creeps[result]:
        print("[spawning] Invalid response from createCreep: {}".format(result))
    else:
        Memory.role_counts[role] += 1


def random_four_digits():
    # JavaScript trickery here - TODO: pythonize
    return Math.floor((1 + Math.random()) * 0x10000).toString(16).substring(1)
