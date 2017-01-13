def main():
    global _memory_init
    # This check is here in case it's a global reset, and we've already initiated memory.
    if _memory_init is None:
        init_memory()

    records.prep_recording()
    records.start_main_record()
    records.record_memory_amount(_memory_init)
    _memory_init = None

    records.start_record()

    if 'meta' not in Memory:
        Memory.meta = {"pause": False, "quiet": False, "friends": []}

    bucket_tier = math.floor((Game.cpu.bucket - 1) / 1000)  # -1 so we don't count max bucket as a separate tier
    if bucket_tier != Memory.meta.last_bucket and bucket_tier:  # and bucket_tier to avoid problems in simulation
        if bucket_tier > Memory.meta.last_bucket:
            print("[main][bucket] Reached a tier {} bucket.".format(bucket_tier))
            if bucket_tier >= 6:
                del Memory.meta.auto_enable_profiling
        else:
            print("[main][bucket] Down to a tier {} bucket.".format(bucket_tier))
            if bucket_tier <= 1:
                Memory.meta.pause = True
                hive = HiveMind(TargetMind())
                for room in hive.my_rooms:
                    room.defense.set_ramparts(True)
    Memory.meta.last_bucket = bucket_tier

    if Memory.meta.pause:
        if Memory.meta.waiting_for_bucket:
            if Game.gcl.level <= 2 and Game.cpu.bucket > 2000 or Game.cpu.bucket >= 10000:
                print("[paused] Bucket full, resuming next tick.")
                del Memory.meta.pause
                del Memory.meta.waiting_for_bucket
            else:
                print("[paused] Bucket accumulated: {} (used loading code: {})".format(Game.cpu.bucket,
                                                                                       math.floor(Game.cpu.getUsed())))
        elif Game.cpu.bucket <= 5000:
            Memory.meta.waiting_for_bucket = True
        return
    records.finish_record('bucket.check')

    records.start_record()
    flags.move_flags()
    records.finish_record('flags.move')

    records.start_record()
    locations.init()
    if Game.time % 320 == 94:
        locations.clean_old_positions()
    records.finish_record('locations.init')

    records.start_record()

    PathFinder.use(True)

    targets = TargetMind()
    hive = HiveMind(targets)
    context.set_hive(hive)

    records.finish_record('hive.init')

    if Game.time % 320 == 53:
        records.start_record()
        consistency.clear_cache()
        records.finish_record('cache.clean')

    if Game.time % 100000 == 6798:
        records.start_record()
        consistency.complete_refresh(hive)
        records.finish_record('cache.complete-refresh')

    if Game.time % 600 == 550:
        records.start_record()
        mining_paths.cleanup_old_values(hive)
        records.finish_record('mining-paths.cleanup')
    # vv purposefully one tick after the above ^^
    if Game.time % 600 == 551:
        records.start_record()
        building.clean_up_all_road_construction_sites()
        records.finish_record('building.clean-up-road-construction-sites')

    records.start_record()
    hive.poll_all_creeps()
    records.finish_record('hive.poll-creeps')
    if Game.time % 5 == 1 or not _.isEmpty(Memory.hostiles):
        records.start_record()
        deathwatch.start_of_tick_check()
        records.finish_record('deathwatch.check')
        records.start_record()
        # NOTE: this also runs running-away checks and deathwatch checks!
        defense.poll_hostiles(hive, autoactions.running_check_room)
        records.finish_record('defense.poll-hostiles')
    if Game.time % 25 == 7:
        records.start_record()
        defense.cleanup_stored_hostiles()
        records.finish_record('defense.clean-hostiles')

    if not Memory.creeps:
        records.start_record()
        Memory.creeps = {}
        for name in Object.keys(Game.creeps):
            Memory.creeps[name] = {}
        records.finish_record('memfix.create-creep-memory')

    records.start_record()
    hive.find_my_rooms()
    records.finish_record('hive.poll-rooms')

    rooms = hive.my_rooms
    if Game.gcl.level > 1 and Game.cpu.bucket <= 4000:
        rooms = sorted(rooms, lambda r: -r.rcl - r.room.controller.progress / r.room.controller.progressTotal)
        rooms = rooms[:len(rooms) - 1]
    for room in rooms:
        run_room(targets, room)

    records.start_record()
    for room in hive.visible_rooms:
        autoactions.pickup_check_room(room)
    records.finish_record('auto.pickup')
    if Game.time % 50 == 40:
        records.start_record()
        autoactions.cleanup_running_memory()
        records.finish_record('auto.running-memory-cleanup')

    if Game.time % 10000 == 367:
        records.start_record()
        hive.balance_rooms()
        records.finish_record('hive.balance_rooms')

    if Game.cpu.bucket is undefined or Game.cpu.bucket >= 6000 and not Memory.meta.quiet:
        records.start_record()
        hive.sing()
        records.finish_record('hive.sing')

    records.finish_main_record()


def run_room(targets, room):
    """
    :type targets: empire.targets.TargetMind
    :type room: rooms.room_mind.RoomMind
    """
    if room.mem.pause:
        return
    records.start_record()
    room.defense.tick()
    records.finish_record('defense.tick')
    records.start_record()
    room.precreep_tick_actions()
    records.finish_record('room.tick')
    for creep in room.creeps:
        run_creep(room.hive, targets, room, creep)
    if Game.cpu.bucket >= 4500 and (Game.time + room.get_unique_owned_index()) % 50 == 0:
        records.start_record()
        actually_did_anything = room.building.build_most_needed_road()
        if actually_did_anything:
            records.finish_record('building.roads.check-pavement')
        else:
            records.finish_record('building.roads.cache-checks-only')

    records.start_record()
    room.building.place_home_ramparts()
    records.finish_record('building.ramparts')
    for spawn in room.spawns:
        records.start_record()
        spawning.run(room, spawn)
        records.finish_record('spawn.tick')
    records.start_record()
    room.links.tick_links()
    records.finish_record('links.tick')
    if Game.time % 525 == 17:
        records.start_record()
        room.mining.cleanup_old_flag_sitting_values()
        records.finish_record('mining.cleanup_flags')
    records.start_record()
    room.minerals.tick_terminal()
    records.finish_record('terminal.tick')


def run_creep(hive, targets, room, creep):
    """
    :type hive: empire.hive.HiveMind
    :type targets: empire.targets.TargetMind
    :type room: rooms.room_mind.RoomMind
    :type creep: Creep
    """
    if creep.spawning and creep.memory.role != role_temporary_replacing:
        return
    if creep.defense_override:
        return
    records.start_record()
    instance = wrap_creep(hive, targets, room, creep)
    if not instance:
        if creep.memory.role:
            print("[{}][{}] Couldn't find role-type wrapper for role {}!".format(
                creep.memory.home, creep.name, creep.memory.role))
        else:
            print("[{}][{}] Couldn't find this creep's role.".format(creep.memory.home, creep.name))
        role = default_roles[spawning.find_base_type(creep)]
        if role:
            creep.memory.role = role
            instance = wrap_creep(hive, targets, room, creep)
            room.register_to_role(instance)
        else:
            instance = RoleBase(hive, targets, room, creep)
            instance.go_to_depot()
    records.finish_record('hive.wrap-creep')
    creep.wrapped = instance
    records.start_record()
    bef = Game.cpu.getUsed()
    rerun = instance.run()
    if Game.cpu.bucket >= 7000 or Game.cpu.getUsed() - bef < 0.3:
        if rerun:
            rerun = instance.run()
        if rerun:
            rerun = instance.run()
        if rerun:
            print("[{}][{}: {}] Tried to rerun three times!".format(instance.home.name, creep.name,
                                                                    creep.memory.role))
    records.finish_record(creep.memory.role)
