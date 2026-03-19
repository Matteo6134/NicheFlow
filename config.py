"""
Configuration for the Instagram Discovery Tool.
Credentials are loaded from the .env file in the project root.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (same folder as this file)
load_dotenv(Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# Instagram Graph API credentials  (set in .env)
# ---------------------------------------------------------------------------
ACCESS_TOKEN = os.environ["ACCESS_TOKEN"]
IG_USER_ID   = os.environ["IG_USER_ID"]

# ---------------------------------------------------------------------------
# Target hashtags
# Grouped by niche — all will be scanned during discovery
# ---------------------------------------------------------------------------
HASHTAGS = [
    # Core product niche
    "3dprinting",
    "3dprint",
    "3dprintedlamp",
    "3dprintedlight",
    "3dprinteddesign",

    # Design disciplines
    "industrialdesign",
    "productdesign",
    "furnituredesign",
    "interiordesign",
    "lightingdesign",

    # Aesthetic movements
    "minimalism",
    "minimalistdesign",
    "brutalismdesign",
    "brutalism",
    "rawdesign",
    "concretejungle",

    # Community / maker
    "makerspace",
    "fdmprinting",
    "designcommunity",
    "creativedesign",
]

# ---------------------------------------------------------------------------
# Follower filters — target the "micro to mid" creator tier
# ---------------------------------------------------------------------------
MIN_FOLLOWERS =   2_000    # ignore hobby accounts with very small reach
MAX_FOLLOWERS = 500_000    # ignore mega-influencers (low engagement, high cost)

# ---------------------------------------------------------------------------
# Scoring weights — must sum to 1.0
# ---------------------------------------------------------------------------
SCORING_WEIGHTS = {
    "engagement": 0.45,   # ER is the strongest signal
    "followers":  0.25,   # tier fit (sweet spot ~50k)
    "overlap":    0.20,   # how many of our hashtags they appear in
    "website":    0.10,   # proxy for professionalism / brand
}

# ---------------------------------------------------------------------------
# Discovery run defaults
# ---------------------------------------------------------------------------
DISCOVERY_MODE   = "top"    # "top" | "recent" | "both"
MEDIA_PER_TAG    = 50       # posts to pull per hashtag (max 50 per API call)
