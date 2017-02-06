var _IJ_VERSION = 5; // Version - when updated, will re-push changes to client.
var _whitespace_regex = new RegExp('\\s+');
// Injection check (causes client to request full injection if not up to date)
var _inject_check = `
    <script>
        (window._ij != _IJ_VERSION) && $('body').injector().get('Connection').sendConsoleCommand('_ij()')
    </script>
`.py_replace('_IJ_VERSION', str(_IJ_VERSION)).py_replace(_whitespace_regex, '');
// Full injection! Uses jquery & angular JS to create a new section in the client's sidebar.
// The section only includes two 'buttons' by default, 'Enable tracing.' and 'Disable tracing.'
// It should be pretty easily modifiable to add more though!
var _full_injection = `
<script>
    if (window._ij != _IJ_VERSION) {
        window._ij = _IJ_VERSION;
        var ijSendCommand = function (cmd) {
            $('body').injector().get('Connection').sendConsoleCommand('_ij("' + cmd + '")');
        };
        var text = \`
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
        \`;
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
`.replace(_whitespace_regex, ' ').replace('_IJ_VERSION', _IJ_VERSION);
function ij_command(command) {
    if (!command) {
        return _full_injection;
    } else if (command == '+') {
        return 'Enabled tracing!';
    } else if (command == '-') {
        return 'Disabled tracing!';
    } else if (command == 't') {
        Memory ['_ij_timeout'] = Game.time + 1000;
    } else {
        return 'Unknown command: `{}`'.format(command);
    }
};
ij_command.toString = ij_command;
function injection_check() {
    var time = Game.time;
    if (Game.time % 10 == 5) {
        var timeout = Memory ['_ij_timeout'];
        if (timeout) {
            if (timeout > Game.time) {
                return;
            }
            else {
                delete Memory ['_ij_timeout'];
            }
        }
        console.log(_inject_check);
    }
};
global._ij = ij_command;
