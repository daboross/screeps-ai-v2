module.exports = function (grunt) {

    grunt.loadNpmTasks('grunt-screeps');

    grunt.initConfig({
        screeps: {
            options: {
                email: 'daboross@daboross.net',
                password: grunt.file.read(process.env['HOME'] + '/Private/.passwords/screeps'),
                branch: 'v2',
                ptr: grunt.option('ptr') || false
            },
            dist: {
                src: ['dist/*.js']
            }
        }
    });
};
