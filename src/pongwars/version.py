"""@package pongwars.version
@brief Single source of truth and release-version helpers.
"""

import re

__version__ = "0.1.5"

_VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def next_patch_version(version: str) -> str:
    """@brief Return the next stable patch version.
    @param version Current semantic version.
    @throws ValueError If version is not a stable three-part semantic version.
    """
    match = _VERSION_RE.fullmatch(version)
    if match is None:
        raise ValueError(f"invalid stable semantic version: {version}")
    major, minor, patch = (int(part) for part in match.groups())
    return f"{major}.{minor}.{patch + 1}"
