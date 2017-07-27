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
__pragma__('noalias', 'values')


def pnk():
    # type: () -> str
    me = stored_data.get_my_username()
    color = _.sample(["PINK", "RED", "BLUE", "ORANGE"])
    return _.sample([
        "Territory of {}. Accept {} as the one true color, or perish.".format(me, color),
        "Territory of {}. Accept {} as the one true color, or perish.".format(me, color),
        "There is only one true color, and it is {}!".format(color),
        "Be {} or be purged!".format(color),
    ])


def auto():
    # type: () -> str
    me = stored_data.get_my_username()
    return _.sample([
        "Powered by BonzAI: https://github.com/bonzaiferroni/bonzAI",
        "Fully automated TooAngel bot: https://github.com/TooAngel/screeps",
        "Territory of {}, an Open Collaboration Society user! (https://github.com/ScreepsOCS)"
            .format(me),
        "{} reserved territory. Deploy.".format(_.sample(["CS", "HV", "SN", "TP"])),
    ])


def coal():
    # type: () -> str
    if len(Memory.meta.friends):
        all = Memory.meta.friends.concat([stored_data.get_my_username()])
    else:
        return "NYXR ❤️ {}".format(stored_data.get_my_username())
    return _.sample([
        lambda: "NYXR ❤️ {} ❤️ {}".format(_.sample(all), _.sample(all)),
        lambda: "NYXR ❤️ {} ❤️ {} ❤️ {}".format(_.sample(all), _.sample(all), _.sample(all)),
        lambda: "NYXR ❤️ {} ❤️ {} ❤️ {} ❤️ {}".format(_.sample(all), _.sample(all), _.sample(all), _.sample(all)),
    ])()


def crcl():
    # type: () -> str
    return _.sample([
        "Territory of INTEGER_MIN",
        "◯",
        "ALL HAIL CIRCLE",
        "◯ ALL HAIL ◯",
        "Don't forget your daily dose of CIRCLE",
        "Don't forget your daily dose of Number.MAX_VALUE",
    ])


def pwrd():
    # type: () -> str
    return _.sample([
        "Powered by Protocol Buffers: https://git.io/vyEdW",
        "Powered by Transcrypt: https://git.io/vyEdZ",
        "Powered by Python: https://git.io/vyEds",
        "Powered by Slack: http://screeps.slack.com/",
    ])


def strw():
    # type: () -> str
    message = _.sample([
        "Territory Of INTEGER_MAX",
        "CIRCLE WORLD!",
        "INTEGER_MAX",
        "Cake!",
        "Delicious Cake!",
        "My Cake Is Real",
        "The Cake Is A Lie",
        "Territory Of STARWAR15432, An INTEGER_MAX MEMBER",
        "Cake, and grief counseling, will be available at the conclusion of the test -GLaDOS",
        "In layman's terms, speedy thing goes in, speedy thing comes out -GLaDOS",
        "It's been a long time. I've been *really* busy being dead. You know, after you MURDERED ME? -GLaDOS",
        "When life gives you lemons, don't make lemonade! Make life take the lemons back! -Portal 2",
        "Do you know who I am? I'm the man whose gonna burn your house down - with the lemons! -Portal 2",
        "It's your friend deadly neurotoxin. If I were you, I'd take a deep breath. And hold it. -Portal 2",
        "See that? That is a potato battery. It's a toy for children. And now she lives in it. -Portal 2",
        "Violence is the last refuge of the incompetent.",
        "Self-education is, I firmly believe, the only kind of education there is.",
        "People who think they know everything are a great annoyance to those of us who do.",
    ])
    return "\"{}\" - starwar15432".format(message)


def lolvl():
    # type: () -> str
    message = _.sample([
        "greetings",
        "hello",
        "Tatramajjhattatā",
    ])
    return message


def rs():
    # type: () -> str
    if Game.gcl.level < 5:
        return lolvl()
    else:
        return _.sample([auto, pnk, coal, crcl, pwrd, strw])()
