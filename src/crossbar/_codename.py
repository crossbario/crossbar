#####################################################################################
#
#  Copyright (c) typedef int GmbH
#  SPDX-License-Identifier: EUPL-1.2
#
#####################################################################################

"""
Crossbar.io release codenames.

Each Crossbar.io CalVer release series (``year.month``) carries a
maintainer-chosen codename, e.g. ``26.6.x`` is "Resistance Is Futile". The
codename is purely additive metadata surfaced in the product title / CLI banner;
it does not affect versioning.

A new codename is assigned per ``year.month`` series at release-prep time (see
the ``prep-release`` recipe in the justfile), alongside the version bump and the
new release signing key.
"""

from typing import Dict, Optional, Tuple

# Map of (year, month) CalVer series -> release codename.
#
# Add a new entry for every new year.month release series. A stable (non-dev)
# release without a codename is rejected by the release gate (see
# crossbar/test/test_codename.py).
_CODENAMES: Dict[Tuple[int, int], str] = {
    (26, 6): "Resistance Is Futile",
    (26, 7): "Shields Up",
    (26, 9): "Poke The Bear",
}


def get_codename(version: Optional[str] = None) -> Optional[str]:
    """
    Look up the release codename for a Crossbar.io CalVer version string.

    :param version: CalVer version string like ``"26.6.1"`` or
        ``"26.6.1.dev1"``. Defaults to the running ``crossbar.__version__``.
    :returns: The codename for the version's ``(year, month)`` series, or
        ``None`` if no codename is assigned (e.g. a development build, or a
        release that has not been named yet). Never raises.
    """
    if version is None:
        import crossbar

        version = crossbar.__version__

    try:
        parts = version.split(".")
        year = int(parts[0])
        month = int(parts[1])
    except (AttributeError, IndexError, ValueError):
        return None

    return _CODENAMES.get((year, month))


def get_codename_suffix(version: Optional[str] = None) -> str:
    """
    Return the codename as a title/banner suffix, e.g. ``" — Resistance Is
    Futile"``, or the empty string when no codename is assigned.

    :param version: see :func:`get_codename`.
    """
    codename = get_codename(version)
    return " — {}".format(codename) if codename else ""
