from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')

_VERSION = 8

_whitespace_regex = __new__(RegExp('\s+'))

_inject_check = (
    """
        <script>
            $('body').injector().get('Connection').sendConsoleCommand('_inject(' + (window._ij == _VERSION) + ')')
        </script>
    """.replace('_VERSION', str(_VERSION)).replace(_whitespace_regex, '')
)

_full_injection = (
    """
    <script>
        if (window._ij != _VERSION) {
            window._ij = _VERSION;
            var ijSendCommand = function (cmd, arg) {
                $('body').injector().get('Connection').sendConsoleCommand('_inject("' + cmd + '", "' + arg + '")');
            };
            var text = `
            <app:aside-block heading="Nyxr Options"
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
            `;
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
    """.replace(_whitespace_regex, ' ').replace('_VERSION', str(_VERSION))
)


def injection_command(command, room_name):
    if not command:
        return _full_injection
    elif command == 'enable-visuals':
        options_mem = Memory['nyxr_options']
        if not options_mem:
            options_mem = Memory['nyxr_options'] = {}
        options_mem[room_name] = Game.time + 100
        return "Visuals enabled for {}.".format(room_name)
    elif command == 'disable-visuals':
        Memory['nyxr_options'] = {'_inject_timeout': Game.time + 1000}
        return "Visuals disabled."
    elif command is True:
        options_mem = Memory['nyxr_options']
        if not options_mem:
            options_mem = Memory['nyxr_options'] = {}
        options_mem['_inject_timeout'] = Game.time + 1000
    else:
        return "Unknown command: `{}`".format(command)


def injection_check():
    if Game.time % 10 == 5:
        options_mem = Memory['nyxr_options']
        if options_mem:
            timeout = options_mem['_inject_timeout']
            if timeout:
                if timeout > Game.time:
                    return
                else:
                    del options_mem['_inject_timeout']
            any_alive = False
            for key in Object.keys(options_mem):
                if options_mem[key] < Game.time:
                    del options_mem[key]
                else:
                    any_alive = True
            if not any_alive:
                del Memory['nyxr_options']
        print(_inject_check)


js_global._inject = injection_command
