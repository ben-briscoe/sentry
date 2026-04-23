from __future__ import annotations

import re


def canonical_mission_mode( mission_mode: str | None ) -> str:
    if mission_mode is None:
        return ""

    raw = mission_mode.strip()
    if raw == "":
        return ""

    last_segment = raw.split( "::" )[ -1 ].split( "." )[ -1 ].strip()
    if last_segment == "":
        last_segment = raw

    normalized = re.sub( r"([a-z0-9])([A-Z])", r"\1_\2", last_segment )
    normalized = re.sub( r"[^A-Za-z0-9]+", "_", normalized )
    normalized = re.sub( r"_+", "_", normalized ).strip( "_" )
    return normalized.upper()


def mode_contains( mission_mode: str | None, *tokens: str ) -> bool:
    canonical = canonical_mission_mode( mission_mode )
    raw_upper = ( mission_mode or "" ).upper()
    return any( token in canonical or token in raw_upper for token in tokens )
