from empire import stored_data
from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')


def rs():
    return _.sample([
        "Powered by BonzAI: https://github.com/bonzaiferroni/bonzAI",
        "◯",
        "Territory of INTEGER_MIN",
        "Territory of {}, an Open Collaboration Society user! (https://github.com/ScreepsOCS)"
            .format(stored_data.get_my_username()),
        "Territory of {}, an Open Collaboration Society user! (https://github.com/ScreepsOCS)"
            .format(_.sample(Memory.meta.friends) or "Universal™"),
        "Fully automated TooAngel bot: https://github.com/TooAngel/screeps",
        "Powered by Protocol Buffers: https://git.io/vyEdW",
        "Powered by Transcrypt: https://git.io/vyEdZ",
        "Powered by Python: https://git.io/vyEds",
        "Powered by Slack: http://screeps.slack.com/",
    ])
