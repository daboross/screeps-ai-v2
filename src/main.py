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


def _calc_early_exit_cpu():
    # type: () -> int
    if Game.cpu.tickLimit == 500:
        return 450
    else:
        return max(Game.cpu.limit, Game.cpu.tickLimit - 150, int((Game.cpu.limit + Game.cpu.tickLimit) / 2))


_early_exit_cpu = _calc_early_exit_cpu()


def real_main():
    if Game.cpu.getUsed() > _early_exit_cpu:
        print("[main] used {} (>= {}) CPU parsing code - exiting"
              .format(Game.cpu.getUsed(), _early_exit_cpu))
    elif Game.cpu.bucket < Game.cpu.limit:
        print("[main] bucket ({}) has less than cpu limit ({}) - exiting directly after parsing"
              .format(Game.cpu.bucket, Game.cpu.limit))
    import main_logic
    main_logic.main()


module.exports.loop = real_main
