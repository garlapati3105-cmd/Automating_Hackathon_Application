"""
Location filtering and priority sorting functions for Hackathon Hunter.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hackathon_hunter.models.hackathon import Hackathon

# Set of lowercase keywords (cities, states, UTs) that identify India.
_INDIA_KEYWORDS = {
    "india", "telangana", "hyderabad", "secunderabad", "warangal", "bengaluru", "bangalore",
    "karnataka", "mysore", "mumbai", "maharashtra", "pune", "nagpur", "thane", "pimpri",
    "chinchwad", "nasik", "navi mumbai", "aurangabad", "solapur", "delhi", "noida",
    "gurgaon", "gurugram", "haryana", "faridabad", "ghaziabad", "uttar pradesh",
    "lucknow", "kanpur", "agra", "varanasi", "meerut", "allahabad", "prayagraj",
    "chennai", "tamil nadu", "coimbatore", "madurai", "salem", "trichy", "kolkata",
    "west bengal", "newtown", "howrah", "darjeeling", "ahmedabad", "gujarat",
    "surat", "vadodara", "rajkot", "gandhinagar", "jaipur", "rajasthan", "jodhpur",
    "udaipur", "kota", "indore", "madhya pradesh", "bhopal", "gwalior", "jabalpur",
    "patna", "bihar", "gaya", "muzaffarpur", "ludhiana", "punjab", "amritsar",
    "jalandhar", "visakhapatnam", "vizag", "andhra pradesh", "vijayawada",
    "guntur", "nellore", "tirupati", "thiruvananthapuram", "kerala", "kochi",
    "trivandrum", "calicut", "kozhikode", "thrissur", "raipur", "chhattisgarh",
    "bilaspur", "guwahati", "assam", "dibrugarh", "chandigarh", "bhubaneswar",
    "odisha", "cuttack", "rourkela", "dehradun", "uttarakhand", "haridwar",
    "ranchi", "jharkhand", "jamshedpur", "dhanbad", "jammu", "srinagar",
    "goa", "panaji", "madgaon", "shimla", "himachal pradesh", "imphal", "manipur",
    "shillong", "meghalaya", "aizawl", "mizoram", "kohima", "nagaland", "gangtok",
    "sikkim", "itagar", "arunachal", "tripura", "agartala", "puducherry",
    "pondicherry", "port blair", "andaman", "nicobar", "kavaratti", "lakshadweep",
    "daman", "diu", "dadra", "nagar haveli", "ladakh", "leh", "kargil"
}


def is_india_hackathon(location: str | None) -> bool:
    """
    Return True if the location is in India.
    
    Checks for the "IN" country code or any Indian cities/states.
    """
    if not location:
        return False
        
    loc_lower = location.lower().strip()
    
    # Check for direct "india"
    if "india" in loc_lower:
        return True
        
    # Check for IN country code using word boundaries to avoid matching strings like
    # "International" or "Internet".
    if re.search(r'\b(in)\b', loc_lower):
        return True
        
    # Tokenize location string by non-alphabetic characters and check keywords
    tokens = re.findall(r'[a-z]+', loc_lower)
    for token in tokens:
        if token in _INDIA_KEYWORDS:
            return True
            
    return False


def is_hyderabad_hackathon(location: str | None) -> bool:
    """Return True if the location refers to Hyderabad."""
    if not location:
        return False
    loc_lower = location.lower().strip()
    return "hyderabad" in loc_lower or "hyd" in loc_lower


def hackathon_priority_key(h: Hackathon, priority_city: str = "hyderabad") -> tuple[int, int]:
    """
    Return a sort key for a hackathon.
    
    Priority order (ascending, lower comes first):
      Primary key (priority_group):
        0: Priority city (Hyderabad)
        1: Other India locations
        2: Online/Worldwide hackathons
        3: All other locations
      Secondary key (offline_first):
        0: Offline (in-person)
        1: Online
    """
    loc = h.location
    loc_lower = loc.lower().strip() if loc else ""
    
    # Check if online
    is_online = bool(h.is_online or "online" in loc_lower or not loc)
    offline_val = 1 if is_online else 0
    
    # 1. Priority City check
    if loc and (priority_city in loc_lower or (priority_city == "hyderabad" and "hyd" in loc_lower)):
        priority_group = 0
    # 2. Other India check
    elif is_india_hackathon(loc):
        priority_group = 1
    # 3. Online check
    elif is_online:
        priority_group = 2
    # 4. Others
    else:
        priority_group = 3
        
    return (priority_group, offline_val)
