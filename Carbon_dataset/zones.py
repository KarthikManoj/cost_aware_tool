"""Cloud region to ElectricityMaps zone mapping, shared by carbon_collect.py
and renewable_collect.py so both use the same zones.

India regions use IN-WE (Western India), not the coarser all-India IN
average, since that would misstate intensity for Mumbai/Pune workloads.
Singapore has no sub-national split, so SG is already correct.
"""

from __future__ import annotations


# (cloud, cloud region, ElectricityMaps zone)
REGIONS: list[tuple[str, str, str]] = [
    ("AWS", "ap-south-1", "IN-WE"),
    ("AWS", "ap-southeast-1", "SG"),
    ("Azure", "Central India", "IN-WE"),
    ("Azure", "Southeast Asia", "SG"),
]

# Zones too coarse to use -- would silently misstate emissions.
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
