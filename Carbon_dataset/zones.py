"""Cloud region to ElectricityMaps zone mapping.

Single source of truth for both `carbon_collect.py` and `renewable_collect.py`
so the two datasets can never be fetched for different zones.

Zone choice matters. ElectricityMaps exposes both a national Indian zone
(`IN`) and finer-grained regional grids. `IN` is the all-India average, which
blends the coal-heavy eastern grid with the comparatively cleaner western
grid and therefore misstates the carbon intensity actually seen by workloads
running in Mumbai or Pune.

    AWS ap-south-1   -> Mumbai, Maharashtra      -> IN-WE (Western India)
    Azure Central India -> Pune, Maharashtra     -> IN-WE (Western India)
    AWS ap-southeast-1  -> Singapore             -> SG
    Azure Southeast Asia -> Singapore            -> SG

Singapore has no sub-national decomposition, so `SG` is already the correct
granularity there.
"""

from __future__ import annotations


# (cloud, cloud region, ElectricityMaps zone)
REGIONS: list[tuple[str, str, str]] = [
    ("AWS", "ap-south-1", "IN-WE"),
    ("AWS", "ap-southeast-1", "SG"),
    ("Azure", "Central India", "IN-WE"),
    ("Azure", "Southeast Asia", "SG"),
]

# Zones that must never be used: they are coarser than the deployment region
# and would silently produce misleading emission estimates.
DEPRECATED_ZONES: dict[str, str] = {
    "IN": "IN-WE",
}


def validate_regions(regions: list[tuple[str, str, str]] = REGIONS) -> None:
    """Raise if any region is mapped to a zone that is too coarse."""
    for cloud, region, zone in regions:
        if zone in DEPRECATED_ZONES:
            raise ValueError(
                f"{cloud} {region} is mapped to the coarse zone '{zone}'. "
                f"Use '{DEPRECATED_ZONES[zone]}' instead -- '{zone}' is a "
                "national average and misstates regional carbon intensity."
            )


def unique_zones(regions: list[tuple[str, str, str]] = REGIONS) -> list[str]:
    """Distinct zones, preserving declaration order."""
    seen: list[str] = []
    for _, _, zone in regions:
        if zone not in seen:
            seen.append(zone)
    return seen
