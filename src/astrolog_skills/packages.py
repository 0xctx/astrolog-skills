"""Install hints: which package manager this Linux uses, and the one command that installs a tool with it."""

from __future__ import annotations

import sys
from pathlib import Path

MANAGERS = (  # (distribution ids, the manager's install command)
    (("fedora", "rhel", "centos"), "sudo dnf install"),
    (("debian", "ubuntu"), "sudo apt install"),
    (("arch",), "sudo pacman -S"),
    (("suse", "opensuse"), "sudo zypper install"),
    (("alpine",), "sudo apk add"),
)


def install_command(os_release: str | None = None) -> str | None:
    """'sudo dnf install', 'sudo apt install' … for this Linux (from /etc/os-release), or None if unknown."""
    text = os_release
    if text is None:
        try:
            text = Path("/etc/os-release").read_text()
        except OSError:
            text = ""
    ids = " ".join(
        line.split("=", 1)[1].strip().strip('"').lower()
        for line in text.splitlines()
        if line.startswith(("ID=", "ID_LIKE="))
    )
    return next((cmd for names, cmd in MANAGERS if any(n in ids for n in names)), None)


def hint(names: dict[str, str], mac: str, windows: str, otherwise: str, os_release: str | None = None) -> str:
    """The install line for a tool whose package is named `names[manager]` ('dnf', 'apt', 'pacman', 'zypper', 'apk';
    '*' for all), on macOS, Windows, or a known Linux; `otherwise` when the system isn't recognised."""
    if sys.platform == "darwin":
        return mac
    if sys.platform == "win32":
        return windows
    cmd = install_command(os_release)
    if cmd is None:
        return otherwise
    manager = cmd.split()[1]
    return f"{cmd} {names.get(manager, names.get('*', ''))}".strip()
