from utilities.screeps_constants import *

__pragma__('noalias', 'name')

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

default_gather_moving_to_storage = (["get", "some", "energy"], False)
default_gather_moving_between_rooms = (["going", "where", "exactly?"], False)
default_gather_storage_withdraw_ok = (["k"], False)
default_gather_no_sources = (["no sources", "!!!"], False)
default_gather_moving_to_energy = (["get", "some", "energy"], False)
default_gather_unknown_result_pickup = (["AAAAhhhh", "!!!???", "(pickup)"], False)
default_gather_energy_pickup_ok = (["k"], False)
default_gather_moving_to_container = (["get", "some", "energy"], False)
default_gather_container_withdraw_ok = (["k"], False)
default_gather_unknown_result_withdraw = (["AAAAhhhh", "!!!???", "(withdraw)"], False)
default_gather_moving_to_source = (["gotta", "get", "some", "coal"], False)
default_gather_source_harvest_ok = _we_are_miners
default_gather_source_harvest_ner = (["just", "chillin", None], False)
default_gather_unknown_result_harvest = (["AAAAhhhh", "!!!???", "(harvest)"], False)

upgrading_controller_not_owned = (["not", "ours", "to", "upgrade!"], False)
upgrading_ok = (["U"], False)
upgrading_moving_to_controller = (["U"], False)
upgrading_unknown_result = (["AAAAhhhh", "!!!???", "(upgrade)"], False)

tower_fill_moving_to_tower = (["tower", "fill", "regiment", "reporting", "for", "duty"], False)
tower_fill_ok = (["T. F."], False)
tower_fill_unknown_result = (["AAAAhhhh", "!!!???", "(transfer)", "(tower)"], False)

spawn_fill_moving_to_target = (["X"], False)
spawn_fill_ok = (["I", "do", "care"], False)
spawn_fill_unknown_result = (["AAAAhhhh", "!!!???", "(transfer)", "spawn_fill"], False)

building_repair_target = (["gonna", "fix", "ah", "{}"], False)
building_build_target = (["gonna", "build", "ah", "{}"], False)

dedi_miner_moving = (["let's", "!GO!", None], False)
dedi_miner_ok = _we_are_miners
dedi_miner_ner = (["just", "chillin", "with", "our", "friends", None], False)
dedi_miner_unknown_result = (["AAAAhhhh", "!!!???", "(harvest)", "dedi_miner"], False)

local_hauler_no_source = (["I have", "no source", None], True)
local_hauler_no_miner = (["I can't", "find {}."], True)
local_hauler_no_miner_name = (["No miner", "at {}"], True)
local_hauler_moving_to_miner = (["coming", "to", "get", "some", None], False)
local_hauler_waiting = (["just", "chillin", None, "man", None], False)
local_hauler_pickup_ok = (["got it"], False)
local_hauler_pickup_unknown_result = (["AAAAhhhh", "!!!???", "(pickup)", "(hauler)"], False)
local_hauler_no_storage = (["don't", "got", "anywhere", "to", "put", "this!", None], False)
local_hauler_moving_to_storage = (["bringing", "the", "goods"], False)
local_hauler_transfer_ok = (["k"], False)
local_hauler_storage_full = (["don't", "got", "anywhere", "to", "put", "this!", None], False)
local_hauler_transfer_unknown_result = (["AAAAhhhh", "!!!???", "(transfer)", "(hauler)"], False)

remote_miner_no_flag = (["I have", "nowhere", "to go!"], False)
remote_miner_moving = (["heading", "to", "the", "mines"], False)
remote_miner_flag_no_source = (["hey", "man", "this", "isn't", "right!"], False)
remote_miner_ok = _we_are_miners
remote_miner_ner = (["chill", "man", None], False)
remote_miner_unknown_result = (["AAAAhhhh", "!!!???", "(harvest)", "remote"], False)

remote_hauler_no_source = (["just", "give me", "somewhere", "to go", "already!", None], False)
remote_hauler_source_no_miner = (["where", "is the", "miner", "at?"], False)
remote_hauler_moving_to_miner = (["heading", "to", "the", "mines"], False)
remote_hauler_ner = (["alright", "alright", "i'm", "cool", None, None], False)
remote_hauler_pickup_ok = (["k"], False)
remote_hauler_pickup_unknown_result = (["AAAAhhhh", "!!!???", "(pickup)", "(remote)"], False)
remote_hauler_no_home_storage = (["don't", "got", "anywhere", "to", "put", "this!", None], False)
remote_hauler_moving_to_storage = (["bringing", "the", "goods", "to a", "{}"], False)
remote_hauler_transfer_ok = (["k"], False)
remote_hauler_storage_full = (["don't", "got", "anywhere", "to", "put", "this!", None], False)
remote_hauler_transfer_unknown_result = (["AAAAhhhh", "!!!???", "(transfer)", "(remote)"], False)

remote_reserve_moving = (["gonna", "stake", "a", "claim", None], False)
remote_reserve_reserving = (["stakin", "a", "claim", None], False)

link_manager_something_not_found = (["where", "do", "I", "go???", None], True)
link_manager_moving = (["i'll", "find", "it", "eventually"], False)
link_manager_ok = (["and", "I", "threw", "it", "on", "the", "ground!"], False)
link_manager_storage_full = (["it's", "full,", None, "Jim", None], False)
link_manager_unknown_result = (["AAAAhhhh", "!!!???", "link_store"], False)

cleanup_found_energy = (["{}, {}"], True)
