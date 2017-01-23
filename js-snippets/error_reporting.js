function report_error(place, err, description) {
    let err_description;
    if (err == undefined) {
        if (err === null) {
            err_description = 'null error';
        } else if (err === undefined) {
            err_description = 'undefined error';
        } else {
            err_description = err + ' error';
        }
    } else if (err.stack == undefined) {
        err_description = `error has undefined stack: ${err}`;
    } else {
        err_description = `error '${err}' has stack:\n${err.stack}`;
    }
    let msg = `[${place}][${Game.time}] Error: ${description}\n${err_description}`;
    console.log(msg);
    Game.notify(msg);
    if (err == undefined) {
        throw err;
    }
}
// usage
try {
} catch (e) {
    report_error('rooms', e, `Error running room ${room.name}`);
}