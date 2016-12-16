from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')

_we_are_miners = (
    [
        "We", "are", "miners,", "hard", "rock", "miners", None,
        "To", "the", "shaft", "house", "we", "must", "go", None,
        "Pour", "your", "bottles", "on", "our", "shoulders", None,
        "We", "are", "marching", "to", "the", "slow", None,
        "On", "the", "line", "boys,", "on", "the", "line", "boys", None,
        "Drill", "your", "holes", "and", "stand", "in", "line", None,
        "'til", "the", "shift", "boss", "comes", "to", "tell", "you", None,
        "You", "must", "drill", "her", "out", "on", "top", None,
        "Can't", "you", "feel", "the", "rock", "dust", "in", "your", "lungs?", None,
        "It'll", "cut", "down", "a", "miner", "when", "he", "is", "still", "young", None,
        "Two", "years", "and", "the", "silicosis", "takes", "hold", None,
        "and", "I", "feel", "like", "I'm", "dying", "from", "mining", "for", "gold", None,
        "Yes,", "I", "feel", "like", "I'm", "dying", "from", "mining", "for", "gold", None, None, None,
    ],
    True
)

base_no_role = (["No role", "!!!"], True)

upgrading_controller_not_owned = (["not", "ours", "to", "upgrade!"], False)
upgrading_ok = (["U"], False)
upgrading_moving_to_controller = (["U"], False)
upgrading_unknown_result = (["AAAAhhhh", "!!!???", "(upgrade)"], False)
upgrading_upgrading_paused = (["still", "recovering"], False)

tower_fill_moving_to_tower = (["tower", "fill", "regiment", "reporting", "for", "duty"], False)
tower_fill_ok = (["T. F."], False)
tower_fill_unknown_result = (["AAAAhhhh", "!!!???", "(transfer)", "(tower)"], False)

spawn_fill_moving_to_target = (["X"], False)
spawn_fill_ok = (["I", "do", "care"], False)
spawn_fill_unknown_result = (["AAAAhhhh", "!!!???", "(transfer)", "spawn_fill"], False)

building_repair_target = (["gonna", "fix", "ah", "{}"], False)
building_build_target = (["gonna", "build", "ah", "{}"], False)

energy_miner_moving = (["heading", "to", "the", "mines"], False)
energy_miner_flag_no_source = (["hey", "man", "this", "isn't", "right!"], False)
energy_miner_ok = _we_are_miners
energy_miner_ner = (["chill", "man", None], False)
energy_miner_unknown_result = (["AAAAhhhh", "!!!???", "(harvest)", "remote"], False)

remote_reserve_moving = (["gonna", "stake", "a", "claim", None], False)
remote_reserve_reserving = (["stakin", "a", "claim", None], False)

link_manager_something_not_found = (["where", "do", "I", "go???", None], True)
link_manager_moving = (["i'll", "find", "it", "eventually"], False)
link_manager_ok = (["and", "I", "threw", "it", "on", "the", "ground!"], False)
link_manager_storage_full = (["it's", "full,", None, "Jim", None], False)
link_manager_storage_empty = (["it's", "empty,", None, "Jim", None], False)
link_manager_unknown_result = (["AAAAhhhh", "!!!???", "link_store"], False)

cleanup_found_energy = (["{}, {}"], True)
recycling = (["I forfeit", "my life"], False)
