function fit_num_sections(needed, maximum, extra_initial, min_split) {
    if (min_split === undefined) {
        min_split = 1;
        if (extra_initial === undefined) {
            extra_initial = 0;
        }
    }

    if (maximum <= 1) {
        return maximum;
    }
    let num = min_split;
    let trying = Infinity;
    while (trying > maximum) {
        trying = Math.ceil(needed / num - extra_initial);
        num++;
    }
    return trying;
}