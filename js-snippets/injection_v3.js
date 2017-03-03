"use strict";

var _VERSION = 8; // Version - when updated, will re-push changes to client.
var _whitespace_regex = new RegExp('\\s+');

// Injection check (causes client to request full injection if not up to date)
var _inject_check = `
        <script>
            if (!window['_SPECIFIC_KEY']) {
                $('body').injector().get('Connection').sendConsoleCommand('_inject(' + (window._ij == _VERSION) + ')');
                window['_SPECIFIC_KEY'] = _VERSION;
            }
        </script>
`.replace('_VERSION', _VERSION).replace(_whitespace_regex, '');

// Full injection! Uses jquery & angular JS to create a new section in the client's sidebar.
// The section only includes two 'buttons' by default, 'Enable tracing.' and 'Disable tracing.'
// It should be pretty easily modifiable to add more though!
var _full_injection = `
    <script>
        if (window._ij != _VERSION) {
            window._ij = _VERSION;
            var ijSendCommand = function (cmd, arg) {
                $('body').injector().get('Connection').sendConsoleCommand('_inject("' + cmd + '", "' + arg + '")');
            };
            var text = \`
            <app:aside-block heading="Visual Options"
                    visibility-model="Room.asidePanels.options"
                    class="ij-options ng-isolate-scope ng-scope">
                <button class="md-raised md-button md-ink-ripple"
                        type="button"
                        md-ink-ripple="#FF0000"
                        ng-click="ijSend('enable-visuals')">
                    Enable Visualizations
                </button>
                <br>
                <button class="md-raised md-button md-ink-ripple"
                        type="button"
                        md-ink-ripple="#FF0000"
                        ng-click="ijSend('disable-visuals')">
                    Disable Visualizations
                </button>
            </app:aside-block>
            \`;
            function addOptions(ij_options, aside_content) {
                ij_options.remove();
                aside_content.each(function () {
                    var aside = $(this);
                    aside.injector().invoke(['$compile', function ($compile) {
                        var scope = aside.scope();
                        scope.ijSend = (cmd) => ijSendCommand(cmd, scope.Room.roomName);
                        aside.append($compile(text)(scope));
                    }]);
                });
            }
            addOptions($(".ij-options"), $('.aside-content'));
            var timeoutID = setInterval(function () {
                if (window._ij != _VERSION) {
                    clearInterval(timeoutID);
                    return;
                }
                var ij_options = $('.ij-options');
                if (ij_options.length == 0) {
                    var aside_content = $('.aside-content');
                    if (aside_content.length > 0) {
                        addOptions(ij_options, aside_content);
                    }
                }
            }, 1000);
        }
    </script>
`.replace(_whitespace_regex, ' ').replace('_VERSION', _VERSION);

const _INJECTION_DELAY = 1000; // How long to wait before trying to inject again after successfully injecting.
const _VISUAL_TIMEOUT = 100; // How long to have visuals stay enabled in a room after being initialy enabled

/// Get a random 4-digit key.
function random_digits() {
    return Math.floor((1 + Math.random()) * 65536).toString(16).substring(1);
}

// Injection command exposed to console
function injection_command(command, room_name) {
    if (!command) {
        var options_mem = Memory['visuals'];
        if (!options_mem) {
            options_mem = Memory['visuals'] = {};
        }
        options_mem['_inject_timeout'] = Game.time + _INJECTION_DELAY;
        return _full_injection;
    } else if (command == 'enable-visuals') {
        var options_mem = Memory['visuals'];
        if (!options_mem) {
            options_mem = Memory['visuals'] = {};
        }
        options_mem[room_name] = Game.time + _VISUAL_TIMEOUT;
        return 'Visuals enabled for {}.'.format(room_name);
    } else if (command == 'disable-visuals') {
        Memory['visuals'] = {'_inject_timeout': Game.time + _INJECTION_DELAY};
        return 'Visuals disabled.';
    } else if (command === true) {
        var options_mem = Memory['visuals'];
        if (!options_mem) {
            options_mem = Memory['visuals'] = {};
        }
        options_mem['_inject_timeout'] = Game.time + _INJECTION_DELAY;
        return `injection time out (command: ${command}, tick: ${Game.time})`;
    } else {
        return `Unknown command: '${command}'`;
    }
};
function injection_check() {
    if (Game.time % 10 == 5) {
        var options_mem = Memory['visuals'];
        if (options_mem) {
            var timeout = options_mem['_inject_timeout'];
            if (timeout) {
                if (timeout > Game.time) {
                    return;
                } else {
                    delete options_mem['_inject_timeout'];
                }
            }
            var any_alive = false;
            for (var key in options_mem) {
                if (options_mem[key] < Game.time) {
                    delete options_mem[key];
                }
                else {
                    var any_alive = true;
                }
            }
            if (!any_alive) {
                delete Memory['visuals'];
            }
        }
        var specific_key = naming.random_digits();
        console.log(_inject_check.replace('_SPECIFIC_KEY', specific_key));
    }
};
global._inject = injection_command;
function get_enabled_visual_rooms() {
    var options_mem = Memory['visuals'];
    var result = [];
    if (!options_mem) {
        return result;
    }
    for (var key in options_mem) {
        if (key[0] != '_' && options_mem[key] > Game.time) {
            result.push(key)
        }
    }
    return result;
}

module.exports = {
    'injection_check': injection_check, // run once per tick
    'visual_rooms': get_enabled_visual_rooms, // run once per tick, returns list of room names with visuals enabled.
}
