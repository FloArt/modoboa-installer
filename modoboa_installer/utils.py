"""Utility functions."""

import contextlib
import datetime
import glob
import os
import platform
import random
import shutil
import string
import subprocess
import sys


ENV = {}
BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)


class FatalError(Exception):

    """A simple exception."""

    pass


def user_input(message):
    """Ask something to the user."""
    try:
        from builtins import input
    except ImportError:
        answer = raw_input(message)
    else:
        answer = input(message)
    return answer


def exec_cmd(cmd, sudo_user=None, pinput=None, login=True, **kwargs):
    """Execute a shell command.
    Run a command using the current user. Set :keyword:`sudo_user` if
    you need different privileges.
    :param str cmd: the command to execute
    :param str sudo_user: a valid system username
    :param str pinput: data to send to process's stdin
    :rtype: tuple
    :return: return code, command output
    """
    sudo_user = ENV.get("sudo_user", sudo_user)
    if sudo_user is not None:
        cmd = "sudo {}-u {} {}".format("-i " if login else "", sudo_user, cmd)
    if "shell" not in kwargs:
        kwargs["shell"] = True
    if pinput is not None:
        kwargs["stdin"] = subprocess.PIPE
    capture_output = False
    if "capture_output" in kwargs:
        capture_output = kwargs.pop("capture_output")
    elif not ENV.get("debug"):
        capture_output = True
    if capture_output:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = None
    process = subprocess.Popen(cmd, **kwargs)
    if pinput or capture_output:
        c_args = [pinput] if pinput is not None else []
        output = process.communicate(*c_args)[0]
    else:
        process.wait()
    return process.returncode, output


def dist_name():
    """Try to guess the distribution name."""
    name, version, _id = platform.linux_distribution()
    return "unknown" if not name else name.lower()


def mkdir(path, mode, uid, gid):
    """Create a directory."""
    if not os.path.exists(path):
        os.mkdir(path, mode)
    else:
        os.chmod(path, mode)
    os.chown(path, uid, gid)


def make_password(length=16):
    """Create a random password."""
    return "".join(
        random.SystemRandom().choice(
            string.ascii_letters + string.digits) for _ in range(length))


@contextlib.contextmanager
def settings(**kwargs):
    """Context manager to declare temporary settings."""
    for key, value in kwargs.items():
        ENV[key] = value
    yield
    for key in kwargs.keys():
        del ENV[key]


class ConfigFileTemplate(string.Template):

    """Custom class for configuration files."""

    delimiter = "%"


def backup_file(fname):
    """Create a backup of a given file."""
    for f in glob.glob("{}.old.*".format(fname)):
        os.unlink(f)
    bak_name = "{}.old.{}".format(
        fname, datetime.datetime.now().isoformat())
    shutil.copy(fname, bak_name)


def copy_file(src, dest):
    """Copy a file to a destination and make a backup before."""
    if os.path.isdir(dest):
        dest = os.path.join(dest, os.path.basename(src))
    if os.path.isfile(dest):
        backup_file(dest)
    shutil.copy(src, dest)


def copy_from_template(template, dest, context):
    """Create and copy a configuration file from a template."""
    now = datetime.datetime.now().isoformat()
    with open(template) as fp:
        buf = fp.read()
    if os.path.isfile(dest):
        backup_file(dest)
    with open(dest, "w") as fp:
        fp.write(
            "# This file was automatically installed on {}\n"
            .format(now))
        fp.write(ConfigFileTemplate(buf).substitute(context))


def check_config_file(dest, domain):
    """Create a new installer config file if needed."""
    if os.path.exists(dest):
        return
    printcolor(
        "Configuration file {} not found, creating new one."
        .format(dest), YELLOW)
    with open("installer.cfg.template") as fp:
        buf = fp.read()
    context = {
        "mysql_password": make_password(),
        "modoboa_password": make_password(),
        "amavis_password": make_password(),
        "sa_password": make_password(),
        "domain_name": domain
    }
    with open(dest, "w") as fp:
        fp.write(string.Template(buf).substitute(context))


def has_colours(stream):
    """Check if terminal supports colors."""
    if not hasattr(stream, "isatty"):
        return False
    if not stream.isatty():
        return False  # auto color only on TTYs
    try:
        import curses
        curses.setupterm()
        return curses.tigetnum("colors") > 2
    except:
        # guess false in case of error
        return False


has_colours = has_colours(sys.stdout)


def printcolor(message, color):
    """Print a message using a green color."""
    if has_colours:
        message = "\x1b[1;{}m{}\x1b[0m".format(30 + color, message)
    print(message)


def convert_version_to_int(version):
    """Convert a version string to an integer."""
    number_bits = (8, 8, 16)

    numbers = [int(number_string) for number_string in version.split(".")]
    if len(numbers) > len(number_bits):
        raise NotImplementedError(
            "Versions with more than {0} decimal places are not supported"
            .format(len(number_bits) - 1)
        )
    # add 0s for missing numbers
    numbers.extend([0] * (len(number_bits) - len(numbers)))
    # convert to single int and return
    number = 0
    total_bits = 0
    for num, bits in reversed(list(zip(numbers, number_bits))):
        max_num = (bits + 1) - 1
        if num >= 1 << max_num:
            raise ValueError(
                "Number {0} cannot be stored with only {1} bits. Max is {2}"
                .format(num, bits, max_num)
            )
        number += num << total_bits
        total_bits += bits
    return number
