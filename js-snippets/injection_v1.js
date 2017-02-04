var _IJ_VERSION = 4; // Version - when updated, will re-push changes to client.

// Injection check (causes client to request full injection if not up to date)
var _inject_check = `
<script>
    (window._ij != _IJ_VERSION) && $('body').injector().get('Connection').sendConsoleCommand('_ij')
</script>
`.replace(/\s+/, '').replace('_IJ_VERSION', str(_IJ_VERSION));

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
</script>
`.replace(/\s+/, ' ').replace('_IJ_VERSION', str(_IJ_VERSION));

// The function that's run when a button is clicked. Return value is sent to console output since it's run directly from
// the console.
function ij_command(command) {
    if (command == '+') {
        return 'Enabled tracing!';
    } else if (command == '-') {
        return 'Disabled tracing!';
    } else if (command == 't') {
        Memory ['_ij_timeout'] = Game.time + 1000;
        return "Won't send updates for another 1000 ticks!";
    } else {
        return 'Unknown command: `{}`'.format(command);
    }
};

// Set the function's toString value to the full injection, so the client can just send the simple string `_ij` in order
// to receive an injection.
ij_command.toString = function _injection() {
    return _full_injection;
};

// Make the command accessible.
global._ij = ij_command;

// This function should be run every tick, in order to check if the client is out of date. It will only output the
// 'injection check' string, so it's fairly lightweight.
function injection_check() {
    if (Game.time % 10 == 5) {
        var timeout = Memory ['_ij_timeout'];
        if (timeout) {
            if (timeout > Game.time) {
                return;
            } else {
                delete Memory ['_ij_timeout'];
            }
        }
        console.log(_inject_check);
    }
};
