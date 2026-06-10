"""
Unit tests for India location filtering and Hyderabad prioritisation logic.
"""

from __future__ import annotations

import pytest

from hackathon_hunter.models.hackathon import Hackathon
from hackathon_hunter.notifications.filters import (
    is_india_hackathon,
    is_hyderabad_hackathon,
    hackathon_priority_key,
)


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("Newtown, West Bengal, IN", True),
        ("Newtown, West Bengal, India", True),
        ("Delhi, IN", True),
        ("Mumbai,IN", True),
        ("Bangalore, Karnataka", True),
        ("Hyderabad, Telangana", True),
        ("Hyderabad", True),
        ("Online", False),
        ("", False),
        (None, False),
        ("Toronto, Canada, CA", False),
        ("London, UK", False),
        # Word boundary tests
        ("Interactive GenAI Hackathon", False),  # Contains "in" but not as word
        ("Internet of Things, US", False),      # Contains "in" but not as word
    ],
)
def test_is_india_hackathon(location: str | None, expected: bool):
    assert is_india_hackathon(location) == expected


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("Hyderabad, Telangana", True),
        ("Hyderabad, IN", True),
        ("HYDERABAD", True),
        ("Secunderabad (Hyd), IN", True),
        ("Delhi, India", False),
        ("Bangalore", False),
        (None, False),
    ],
)
def test_is_hyderabad_hackathon(location: str | None, expected: bool):
    assert is_hyderabad_hackathon(location) == expected


def test_hackathon_priority_key():
    h_hyd = Hackathon(
        platform="devfolio",
        name="Hyd Hack",
        url="https://hyd.co",
        location="Hyderabad, IN",
        is_online=False,
    )
    h_hyd_online = Hackathon(
        platform="devfolio",
        name="Hyd Online Hack",
        url="https://hydonline.co",
        location="Hyderabad, Online",
        is_online=True,
    )
    h_india = Hackathon(
        platform="devfolio",
        name="Bengal Hack",
        url="https://bengal.co",
        location="Kolkata, West Bengal, IN",
        is_online=False,
    )
    h_online = Hackathon(
        platform="devpost",
        name="Global Online",
        url="https://online.co",
        location="Online",
        is_online=True,
    )
    h_us = Hackathon(
        platform="mlh",
        name="US Hack",
        url="https://us.co",
        location="Boston, MA, US",
        is_online=False,
    )

    # Sort key order (lower is higher priority)
    assert hackathon_priority_key(h_hyd) == (0, 0)
    assert hackathon_priority_key(h_hyd_online) == (0, 1)
    assert hackathon_priority_key(h_india) == (1, 0)
    assert hackathon_priority_key(h_online) == (2, 1)
    assert hackathon_priority_key(h_us) == (3, 0)

    # Sorting verification (should be offline Hyderabad, online Hyderabad, offline India, online general, offline US)
    to_sort = [h_us, h_online, h_india, h_hyd_online, h_hyd]
    sorted_list = sorted(to_sort, key=hackathon_priority_key)
    assert sorted_list == [h_hyd, h_hyd_online, h_india, h_online, h_us]

