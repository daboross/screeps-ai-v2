function towerDamage (range) {
	if (range > 20) {
		return 150;
	} else if (range < 5) {
		return 600;
	}
	return (25 - range) * 30;
}