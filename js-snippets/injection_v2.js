"use strict";
var _VERSION = 7;// Version - when updated, will re-push changes to client.
var _whitespace_regex = new RegExp('\\s+');
// Injection check (causes client to request full injection if not up to date)
var _inject_check = `
    <script>
        (window._ij != _VERSION) && $('body').injector().get('Connection').sendConsoleCommand('_inject()')
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
            function addOptions() {
                $(".ij-options").remove();
                $('.aside-content').each(function () {
                    var aside = $(this);
                    aside.injector().invoke(['$compile', function ($compile) {
                        var scope = aside.scope();
                        scope.ijSend = (cmd) => ijSendCommand(cmd, scope.Room.roomName);
                        console.log(scope.Room);
                        aside.append($compile(text)(scope));
                    }]);
                });
                ijSendCommand('loaded');
            }
            addOptions();
            var timeoutID = setInterval(function () {
                if (window._ij != _VERSION) {
                    clearInterval(timeoutID);
                    return;
                }
                if ($(".ij-options").length == 0) {
                    addOptions();
                }
            }, 1000);
        }
    </script>
`.replace(_whitespace_regex, ' ').replace('_VERSION', _VERSION);

const _INJECTION_DELAY = 1000; // How long to wait before trying to inject again after successfully injecting.
const _VISUAL_TIMEOUT = 100; // How long to have visuals stay enabled in a room after being initialy enabled

// Injection command exposed to console
function injection_command(command, room_name) {
    if (!command) {
        return _full_injection;
    } else if (command == 'enable-visuals') {
        var options_mem = Memory ['visuals'];
        if (!options_mem) {
            Memory ['visuals'] = options_mem = {};
        }
        options_mem [room_name] = Game.time + 100;
        return 'Visuals enabled for {}.'.format(room_name);
    } else if (command == 'disable-visuals') {
        Memory ['visuals'] = {'_inject_timeout': Game.time + 1000};
        return 'Visuals disabled.';
    } else if (command == 'loaded') {
        var options_mem = Memory ['visuals'];
        if (!options_mem) {
            Memory ['visuals'] = options_mem = {};
        }
        options_mem ['_inject_timeout'] = Game.time + 1000;
    } else {
        return 'Unknown command: `{}`'.format(command);
    }
}
function injection_check() {
    if (Game.time % 10 == 5) {
        var options_mem = Memory ['visuals'];
        if (options_mem) {
            var timeout = Memory ['_inject_timeout'];
            if (timeout) {
                if (timeout > Game.time) {
                    return;
                }
                else {
                    delete Memory ['_inject_timeout'];
                }
            }
            var any_alive = false;
            for (var key in options_mem) {
                if (options_mem [key] < Game.time) {
                    delete options_mem [key];
                } else {
                    var any_alive = true;
                }
            }
            if (!any_alive) {
                delete Memory ['visuals'];
            }
        }
        console.log(_inject_check);
    }
}
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