from constants.memkeys import global_mem_key_next_shard_set_attempt
from empire.hive import HiveMind
from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


def tick_shard_limit_check(hive: HiveMind) -> bool:
    """
    Checks the current tick shard limit to ensure that we don't run out of bucket on a shard
    we have no CPU on.

    :return: True if we should halt execution now, False otherwise.
    """
    if Game.cpu.limit < 5 and Game.shard:
        do_not_attempt_till = Memory[global_mem_key_next_shard_set_attempt]
        if do_not_attempt_till:
            if do_not_attempt_till > Game.time:
                return True
            else:
                del Memory[global_mem_key_next_shard_set_attempt]
        this_shard = Game.shard.name
        current_limits = Game.cpu.shardLimits
        all_shards = Object.keys(current_limits)

        total = 0
        except_me = 0
        for shard in all_shards:
            total += current_limits[shard]
            if shard != this_shard:
                except_me += current_limits[shard]
        ratios = {}
        for shard in all_shards:
            if shard != this_shard:
                ratios[shard] = current_limits[shard] / except_me

        gcl = Game.gcl.level
        per_gcl = total / (gcl + 2)
        owned = len(hive.my_rooms)

        if owned:
            we_need = owned * per_gcl
        else:
            we_need = per_gcl / 2
        the_rest = total - we_need
        new_limits = {}
        for shard in all_shards:
            if shard == this_shard:
                new_limits[shard] = we_need
            else:
                new_limits[shard] = ratios[shard] * the_rest

        msg = (
            "code on shard {} has no CPU allocated!"
            "current-limits={}, "
            "total-allocatable={}, "
            "current-allocated-to-others={}, "
            "owned-here={}, "
            "cpu-per-gcl={}, "
            "we-need-now={}, "
            "planned-limits={}, "
        ).format(
            this_shard,
            JSON.stringify(current_limits),
            total,
            except_me,
            owned,
            per_gcl,
            we_need,
            new_limits,
        )

        print(msg)
        Game.notify(msg)

        result = Game.cpu.setShardLimits(new_limits)
        if result == OK:
            return False
        elif result == ERR_BUSY:
            msg = "code on shard {} has no CPU allocated, and has hit the shard limit set timeout.".format(this_shard)
            print(msg)
            Game.notify(msg)
            Memory[global_mem_key_next_shard_set_attempt] = Game.time + 2048
            return True
        else:
            msg = "setting shard limit on shard {} to {} failed with unknown error: {}".format(
                this_shard, new_limits, result,
            )
            print(msg)
            Game.notify(msg)
    return False
