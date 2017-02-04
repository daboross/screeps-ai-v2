from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')

_IJ_VERSION = 5

_whitespace_regex = __new__(RegExp('\s+'))

_inject_check = (
    """
        <script>
            (window._ij != _IJ_VERSION) && $('body').injector().get('Connection').sendConsoleCommand('_ij()')
        </script>
    """.replace('_IJ_VERSION', str(_IJ_VERSION)).replace(_whitespace_regex, '')
)

_full_injection = (
    """
    <script>
        if (window._ij != _IJ_VERSION) {
            window._ij = _IJ_VERSION;
            var ijSendCommand = function (cmd) {
                $('body').injector().get('Connection').sendConsoleCommand('_ij("' + cmd + '")');
            };
            var text = `
            <app:aside-block heading="IJ Options"
                    visibility-model="Room.asidePanels.options"
                    class="ij-options ng-isolate-scope ng-scope">
                <button class="md-raised md-button md-ink-ripple"
                        type="button"
                        md-ink-ripple="#FF0000"
                        ng-click="ijSend('+')">
                    Enable tracing.
                </button>
                <br>
                <button class="md-raised md-button md-ink-ripple"
                        type="button"
                        md-ink-ripple="#FF0000"
                        ng-click="ijSend('-')">
                    Disable tracing.
                </button>
            </app:aside-block>
            `;
            function addOptions() {
                $(".ij-options").remove();
                $('.aside-content').each(function () {
                    var aside = $(this);
                    aside.injector().invoke(['$compile', function ($compile) {
                        var scope = aside.scope();
                        scope.ijSend = ijSendCommand;
                        aside.append($compile(text)(scope));
                    }]);
                });
                ijSendCommand('t');
            }
            addOptions();
            var timeoutID = setInterval(function () {
                if (window._ij != _IJ_VERSION) {
                    clearInterval(timeoutID);
                    return;
                }
                if ($(".ij-options").length == 0) {
                    addOptions();
                }
            }, 10000);
        }
    </script>
    """.replace(_whitespace_regex, ' ').replace('_IJ_VERSION', str(_IJ_VERSION))
)


def ij_command(command):
    if not command:
        return _full_injection
    elif command == '+':
        return "Enabled tracing!"
    elif command == '-':
        return "Disabled tracing!"
    elif command == 't':
        Memory['_ij_timeout'] = Game.time + 1000
        return "Won't send updates for another 1000 ticks!"
    else:
        return "Unknown command: `{}`".format(command)


ij_command.toString = ij_command  # allow access to stuff via just `_ij` in console.


def check_output_to_console():
    time = Game.time
    if time % 10 == 5:
        timeout = Memory['_ij_timeout']
        if timeout:
            if timeout > Game.time:
                return
            else:
                del Memory['_ij_timeout']
        print(_inject_check)


js_global._ij = ij_command
