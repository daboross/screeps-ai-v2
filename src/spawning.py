from math import floor

import creep_utils
from base import *

__pragma__('noalias', 'name')


def run(spawn):
    if not Memory.no_more_spawning and not spawn.spawning:
        # TODO: extra roles which might need >1000 energy!
        max = min(spawn.room.energyCapacityAvailable, 1000)
        spawn_with_energy(spawn, max)


def spawn_with_energy(spawn, energy):
    if (creep_utils.role_count("harvester") < 2
        and spawn.room.energyAvailable >= 200):
        energy = spawn.room.energyAvailable

    if spawn.room.energyAvailable >= energy:
        role = creep_utils.get_role_name(True)
        if not role:
            Memory.no_more_spawning = True
        if role == "big_harvester":
            if energy < 550:
                if energy % 100 == 0:
                    parts = [MOVE, MOVE]
                    energyUsed = 100
                    while energyUsed <= energy - 100:
                        parts.append(WORK)
                        energyUsed += 100
                    spawn_with_array(spawn, role, parts)
                else:
                    parts = [MOVE]
                    energyUsed = 50
                    while energyUsed <= energy - 100:
                        parts.append(WORK)
                        energyUsed += 100
                    spawn_with_array(spawn, role, parts)
            else:
                parts = [WORK, WORK, WORK, WORK, WORK, MOVE, MOVE]
                spawn_with_array(spawn, role, parts)
        elif energy >= 500:
            parts = []
            part_idea = [MOVE, MOVE, CARRY, WORK]
            num_sections = int(floor(energy / 250))
            for i in range(0, num_sections):
                for part in part_idea:
                    parts.append(part)
            spawn_with_array(spawn, role, parts)
        elif energy >= 400:
            spawn_with_array(spawn, role, [
                MOVE, MOVE, MOVE, CARRY, WORK, WORK
            ])
        elif energy >= 250:
            spawn_with_array(spawn, role, [MOVE, MOVE, CARRY, WORK])
        elif energy >= 200:
            spawn_with_array(spawn, role, [MOVE, CARRY, WORK])


def spawn_with_array(spawn, role, parts):
    name = random_four_digits()
    print("Choosing role {} with parts {}".format(role, parts))
    result = spawn.createCreep(parts, name, {"role": role})
    if result != OK and not Game.creeps[result]:
        print("Invalid response from createCreep: {}".format(result))
    else:
        Memory.role_counts[role] += 1


def random_four_digits():
    # JavaScript trickery here - TODO: pythonize
    return Math.floor((1 + Math.random()) * 0x10000).toString(16).substring(1)
