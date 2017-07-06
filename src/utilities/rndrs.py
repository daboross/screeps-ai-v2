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


def pnk():
    me = stored_data.get_my_username()
    color = _.sample(["PINK", "RED", "BLUE", "ORANGE"])
    return _.sample([
        "Territory of {}. Accept {} as the one true color, or perish.".format(me, color),
        "Territory of {}. Accept {} as the one true color, or perish.".format(me, color),
        "There is only one true color, and it is {}!".format(color),
        "Be {} or be purged!".format(color),
    ]),


def auto():
    me = stored_data.get_my_username()
    return _.sample([
        "Powered by BonzAI: https://github.com/bonzaiferroni/bonzAI",
        "Fully automated TooAngel bot: https://github.com/TooAngel/screeps",
        "Territory of {}, an Open Collaboration Society user! (https://github.com/ScreepsOCS)"
            .format(me),
        "{} reserved territory. Deploy.".format(_.sample(["CS", "HV", "SN", "TP"])),
    ])


def coal():
    if len(Memory.meta.friends):
        all = Memory.meta.friends.concat([stored_data.get_my_username()])
    else:
        return "NYXR ❤️ {}".format(stored_data.get_my_username())
    return _.sample([
        lambda: "NYXR ❤️ {} ❤️ {}".format(_.sample(all), _.sample(all)),
        lambda: "NYXR ❤️ {} ❤️ {} ❤️ {}".format(_.sample(all), _.sample(all), _.sample(all)),
        lambda: "NYXR ❤️ {} ❤️ {} ❤️ {} ❤️ {}".format(_.sample(all), _.sample(all), _.sample(all), _.sample(all)),
    ])(),


def crcl():
    return _.sample([
        "Territory of INTEGER_MIN",
        "◯",
        "ALL HAIL CIRCLE",
        "◯ ALL HAIL ◯",
        "Don't forget your daily dose of CIRCLE",
        "Don't forget your daily dose of Number.MAX_VALUE",
    ])


def pwrd():
    return _.sample([
        "Powered by Protocol Buffers: https://git.io/vyEdW",
        "Powered by Transcrypt: https://git.io/vyEdZ",
        "Powered by Python: https://git.io/vyEds",
        "Powered by Slack: http://screeps.slack.com/",
    ])


def rs():
    return _.sample([auto, pnk, coal, crcl, pwrd])()
