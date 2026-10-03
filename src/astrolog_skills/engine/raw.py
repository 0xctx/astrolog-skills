"""Pass-through: any Astrolog switch, with the profile's pinned settings (and a chart, if given) applied first."""

from __future__ import annotations

from pathlib import Path

from astrolog_skills.astrolog.run import Completed, run
from astrolog_skills.engine.cast import binary_or_raise
from astrolog_skills.engine.moment import Moment
from astrolog_skills.engine.profile import Profile, active, pins

RAW_TIMEOUT = 120  # some Astrolog outputs (searches, long ephemerides) are slow


def raw_argv(switches: list[str], moment: Moment | None = None, profile: Profile | None = None) -> list[str]:
    """Pinned settings first, then the chart, then the user's switches — which win, deliberately."""
    profile = profile or active()
    return [*pins(profile), *(moment.cast_args() if moment else []), *switches]


def raw(
    switches: list[str], moment: Moment | None = None, profile: Profile | None = None, binary: Path | None = None
) -> tuple[list[str], Completed]:
    argv = raw_argv(switches, moment, profile)
    return argv, run(binary or binary_or_raise(), argv, timeout=RAW_TIMEOUT)
