from math import floor

import context
import creep_utils
from constants import *
from screeps_constants import *

__pragma__('noalias', 'name')


def run(spawn):
    if not Memory.meta.no_more_spawning and not spawn.spawning:
        # TODO: pre-pick roles to spawn so we can actually spawn things when we have the energy needed *for them*,
        # not energy needed for the biggest role
        max_energy = min(spawn.room.energyCapacityAvailable, 1300)
        spawn_with_energy(spawn, max_energy)


def spawn_with_energy(spawn, energy):
    # If we have very few harvesters, try to spawn a new one! But don't make it too small, if we already have a big
    # harvester. 150 * work_mass will make a new harvester somewhat smaller than the existing one, but it shouldn't be
    # too bad. We *can* assume that all work_mass at this point is in harvesters, since creep_utils.reassign_roles()
    # will reassign everyone to harvester if there are fewer than 2 harvesters existing.
    if context.room().role_count(role_spawn_fill) < 2 \
            and spawn.room.energyAvailable >= 150 * context.room().work_mass and spawn.room.energyAvailable >= 250:
        energy = spawn.room.energyAvailable

    if spawn.room.energyAvailable >= energy:
        base, role = creep_utils.get_role_name()

        if not role:
            Memory.meta.no_more_spawning = True
            return

        if base is creep_base_big_harvester:
            parts = [MOVE, MOVE]
            num_sections = min(int(floor((energy - 100) / 100)), 5)
            for i in range(0, num_sections):
                parts.append(WORK)
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
        elif base is creep_base_full_miner:
            if energy >= 750:
                spawn_with_array(spawn, role, base, [
                    MOVE, MOVE, MOVE, MOVE, MOVE, WORK, WORK, WORK, WORK, WORK,
                ])
            elif energy >= 550:
                parts = []
                num_move = int(floor((energy - 500) / 50))
                num_work = 5
                for i in range(0, num_move): parts.append(MOVE)
                for i in range(0, num_work): parts.append(WORK)
            else:
                print("[spawning] Not enough energy to create a remote miner!"
                      " This WILL block spawning until it is fixed!")
        elif base is creep_base_hauler:
            parts = []
            section = [CARRY, MOVE]
            num_sections = min(int(floor(energy / 100)), 5)
            for i in range(0, num_sections):
                for part in section:
                    parts.append(part)
            spawn_with_array(spawn, role, base, parts)
        elif base is creep_base_small_hauler:
            parts = []
            section = [CARRY, MOVE]
            num_sections = min(int(floor(energy / 100)), 3)
            for i in range(0, num_sections):
                for part in section:
                    parts.append(part)
            spawn_with_array(spawn, role, base, parts)
        elif base is creep_base_reserving:
            if energy >= 1300:
                spawn_with_array(spawn, role, base, [MOVE, CLAIM, CLAIM, MOVE])
            elif energy >= 650:
                spawn_with_array(spawn, role, base, [MOVE, CLAIM])
            else:
                print("[spawning] Not enough energy to create remote reserve creep!"
                      " This WILL block spawning until it is fixed!")
        elif base is creep_base_defender:
            parts = []
            # MOVE, MOVE, ATTACK, TOUCH = one section = 190
            num_sections = min(int(floor(energy / 190)), 5)
            for i in range(0, num_sections):
                parts.append(TOUGH)
            for i in range(0, num_sections - 1):
                parts.append(MOVE)
            for i in range(0, num_sections):
                parts.append(ATTACK)
            parts.append(MOVE)
            spawn_with_array(spawn, role, base, parts)
        else:
            print("[spawning] Unknown creep base {}!".format(base))


def spawn_with_array(spawn, role, base, parts):
    name = random_four_digits()
    home = context.room().room_name
    print("[spawning] Choosing role {} with parts {}".format(role, parts))
    result = spawn.createCreep(parts, name, {"role": role, "base": base, "home": home})
    if result != OK and not Game.creeps[result]:
        print("[spawning] Invalid response from createCreep: {}".format(result))
    else:
        context.room().add_to_role(role)


def random_four_digits():
    # JavaScript trickery here - TODO: pythonize
    return Math.floor((1 + Math.random()) * 0x10000).toString(16).substring(1)
