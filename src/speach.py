_we_are_miners = [
    "We", "are", "miners,", "hard", "rock", "miners", " - ",
    "To", "the", "shaft", "house", "we", "must", "go", " - ",
    "Pour", "your", "bottles", "on", "our", "shoulders", " - ",
    "We", "are", "marching", "to", "the", "slow", " - ",
    " - ", " - ",
    "On", "the", "line", "boys,", "on", "the", "line", "boys", " - ",
    "Drill", "your", "holes", "and", "stand", "in", "line", " - ",
    "'til", "the", "shift", "boss", "comes", "to", "tell", "you", " - ",
    "You", "must", "drill", "her", "out", "on", "top", " - ",
    " - ", " - ",
    "Can't", "you", "feel", "the", "rock", "dust", "in", "your", "lungs?", " - ",
    "It'll", "cut", "down", "a", "miner", "when", "he", "is", "still", "young", " - ",
    "Two", "years", "and", "the", "silicosis", "takes", "hold", " - ",
    "and", "I", "feel", "like", "I'm", "dying", "from", "mining", "for", "gold", " - ",
    " - ", " - ",
    "Yes,", "I", "feel", "like", "I'm", "dying", "from", "mining", "for", "gold", " . ",
]

base_no_role = ["No role", "!!!"]

default_gather_moving_to_storage = ["get", "some", "energy"]
default_gather_moving_between_rooms = ["going", "where", "exactly?"]
default_gather_storage_withdraw_ok = ["k"]
default_gather_no_sources = ["no sources", "!!!"]
default_gather_moving_to_energy = ["get", "some", "energy"]
default_gather_unknown_result_pickup = ["AAAAhhhh", "!!!???", "(pickup)"]
default_gather_energy_pickup_ok = ["k"]
default_gather_moving_to_container = ["get", "some", "energy"]
default_gather_container_withdraw_ok = ["k"]
default_gather_unknown_result_withdraw = ["AAAAhhhh", "!!!???", "(withdraw)"]
default_gather_moving_to_source = ["gotta", "get", "some", "coal"]
default_gather_source_harvest_ok = _we_are_miners
default_gather_source_harvest_ner = ["just", "chillin", "."]
default_gather_unknown_result_harvest = ["AAAAhhhh", "!!!???", "(harvest)"]

upgrading_controller_not_owned = ["not", "ours", "to", "upgrade!"]
upgrading_ok = ["U"]
upgrading_moving_to_controller = ["U"]
upgrading_unknown_result = ["AAAAhhhh", "!!!???", "(upgrade)"]

tower_fill_moving_to_tower = ["tower", "fill", "regiment", "reporting", "for", "duty"]
tower_fill_ok = ["T. F."]
tower_fill_unknown_result = ["AAAAhhhh", "!!!???", "(transfer)", "(tower)"]

spawn_fill_moving_to_target = ["X"]
spawn_fill_ok = ["I", "do", "care"]
spawn_fill_unknown_result = ["AAAAhhhh", "!!!???", "(transfer)", "spawn_fill"]

building_repair_target = ["gonna", "fix", "ah", "{}"]
building_build_target = ["gonna", "build", "ah", "{}"]

dedi_miner_moving = ["let's", "!GO!", "."]
dedi_miner_ok = _we_are_miners
dedi_miner_ner = ["just", "chillin", "with", "our", "friends", "."]
dedi_miner_unknown_result = ["AAAAhhhh", "!!!???", "(harvest)", "dedi_miner"]

local_hauler_no_source = ["aint", "got", "no", "use", "for", "me", "now", "."]
local_hauler_no_miner = ["where", "my", "guy", "at??"]
local_hauler_moving_to_miner = ["coming", "to", "get", "some", "."]
local_hauler_waiting = ["just", "chillin", ".", "man", "."]
local_hauler_pickup_ok = ["got it"]
local_hauler_pickup_unknown_result = ["AAAAhhhh", "!!!???", "(pickup)", "(hauler)"]
local_hauler_no_storage = ["don't", "got", "anywhere", "to", "put", "this!", "."]
local_hauler_moving_to_storage = ["bringing", "the", "goods"]
local_hauler_transfer_ok = ["k"]
local_hauler_storage_full = ["don't", "got", "anywhere", "to", "put", "this!", "."]
local_hauler_transfer_unknown_result = ["AAAAhhhh", "!!!???", "(transfer)", "(hauler)"]

remote_miner_no_flag = ["I have", "nowhere", "to go!"]
remote_miner_moving = ["heading", "to", "the", "mines"]
remote_miner_flag_no_source = ["hey", "man", "this", "isn't", "right!"]
remote_miner_ok = _we_are_miners
remote_miner_ner = ["chill", "man", ".", ".", ".", "."]
remote_miner_unknown_result = ["AAAAhhhh", "!!!???", "(harvest)", "remote"]

remote_hauler_no_source = ["just", "give me", "somewhere", "to go", "already!", "."]
remote_hauler_source_no_miner = ["where", "is the", "miner", "at?"]
remote_hauler_moving_to_miner = ["heading", "to", "the", "mines"]
remote_hauler_ner = [".", ".", "alright", "alright", "i'm", "chillin"]
remote_hauler_pickup_ok = ["k"]
remote_hauler_pickup_unknown_result = ["AAAAhhhh", "!!!???", "(pickup)", "(remote)"]
remote_hauler_no_home_storage = ["don't", "got", "anywhere", "to", "put", "this!", "."]
remote_hauler_moving_to_storage = ["bringing", "the", "goods"]
remote_hauler_transfer_ok = ["k"]
remote_hauler_storage_full = ["don't", "got", "anywhere", "to", "put", "this!", "."]
remote_hauler_transfer_unknown_result = ["AAAAhhhh", "!!!???", "(transfer)", "(remote)"]

remote_reserve_moving = ["gonna", "stake", "a", "claim", "."]
remote_reserve_reserving = ["gonna", "stake", "a", "claim", "."]
