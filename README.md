Screeps-v2
==========

This repository contains a snapshot of my program written for the JavaScript-based MMO game, screeps.com.

Although screeps uses JS, this repository is, as you've probably noticed, written in Python. In order to accomplish this,
I've used a tool called [transcrypt](transcrypt.com). See the [screeps-starter-python] repository for more info on this.

The `./build.py` script does the majority of the work, from setting up a new environment to building/publishing the
binary to the screeps server. However, you will need to install some dependencies:

- `python-3.5` - Transcrypt works natively with Python 3.5, so you will need this version installed. Python 3.4 is more
  widely available, but will not work for our purposes.
- `pip` - Make sure you have a Python 3.* version of `pip` installed as well. While `pip-3.4` is fine, you do need at
  least that in order to make a `python-3.5` virtualenv. You can check your pip version with `pip --version`, and
  depending on how it was installed, you may need to use `pip3`, `pip-3`, `pip3.4` or `pip-3.4` instead.

After you have those set up, you'll need to install `virtualenv`:

To install virtualenv, use `pip` (or another `pip3*` / `pip-3*` command) as follows:

```
pip install --user virtualenv
```

After that, the rest of the dependencies will be installed upon running `build.py` for the first time.

The only remaining step will be to provide your screeps credentials. To do that, copy `config.default.json` to
a new file `config.json`, and enter your email and password into the config.

Following that, you're all set up! All you need to do now is run `python3 build.py` to compile, collect and deploy code.

[screeps-starter-python]: https://github.com/daboross/screeps-starter-python/
