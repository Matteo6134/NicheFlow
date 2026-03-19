"""
Comment & DM suggestion engine.
Generates personalized, varied suggestions based on creator niche + bio.
No external API needed,template-based with keyword matching.
"""

import random
import re
from typing import Optional


# ---------------------------------------------------------------------------
# Template bank,keyed by niche signal
# ---------------------------------------------------------------------------

COMMENT_TEMPLATES: dict[str, list[str]] = {
    "3dprinting": [
        "The layer quality on this is insane,what slicer settings are you running?",
        "This is exactly the kind of work that makes me love the 3D printing community.",
        "The detail resolution here is seriously impressive. FDM or resin?",
        "Love seeing this level of craft. The finish on this piece is next level.",
        "This is the kind of print that makes people stop scrolling. Really clean work.",
    ],
    "lamp": [
        "The light diffusion on this is perfect,hard to achieve with additive manufacturing.",
        "Really beautiful relationship between form and light here.",
        "The way the material interacts with the light source is so well thought out.",
        "This is exactly what I love about functional design,beauty with purpose.",
        "The shadow patterns this must create at night would be incredible.",
    ],
    "minimalism": [
        "This is what restraint in design looks like. Every element earns its place.",
        "The negative space here is doing so much heavy lifting. Really considered work.",
        "Less is genuinely more here. Beautiful.",
        "The proportion and balance in this piece is really rare to see.",
        "This kind of quiet confidence in design is hard to pull off. Well done.",
    ],
    "brutalism": [
        "The raw material honesty in this is refreshing. No apology for what it is.",
        "Brutalism done right,powerful without being aggressive.",
        "Love the tension between mass and delicacy here.",
        "This reminds me why brutalism never really went away,it just gets reinterpreted.",
        "The material truth in this piece is striking.",
    ],
    "industrialdesign": [
        "The design language here is really coherent,every detail supports the whole.",
        "This is exactly how product design should communicate,visually immediate.",
        "Really strong understanding of form-function relationship here.",
        "The manufacturing logic is visible in the design. That's smart.",
        "Love how the process is embedded in the final aesthetic.",
    ],
    "productdesign": [
        "The design thinking behind this is immediately legible. Really clean.",
        "This is the kind of product that doesn't need words to explain itself.",
        "Great balance between the functional and the expressive.",
        "The material choice here perfectly matches the design intent.",
        "Really considered work,the details make it.",
    ],
    "design": [
        "This is exactly the kind of work that elevates the whole category.",
        "Really strong design language. Immediately recognizable.",
        "The cohesion between all the elements here is impressive.",
        "This kind of intentional design is rare. Really well done.",
        "Love the creative direction on this.",
    ],
}

DM_TEMPLATES: dict[str, list[str]] = {
    "3dprinting": [
        (
            "Hey {name} your work in the 3D printing space is genuinely impressive. "
            "I created grvty, a lamp inspired by the pyramid shape, fully 3D printed as one single piece. "
            "The geometry and light diffusion are something else. Would love to send you one to try out, "
            "no strings attached, just think your audience would find it interesting."
        ),
        (
            "Hi {name}! I came across your work and immediately thought of what we're doing. "
            "grvty is a pyramid inspired lamp, 3D printed as one seamless piece. "
            "Would love to collaborate or just get your honest thoughts. Check out @grvty.std!"
        ),
    ],
    "minimalism": [
        (
            "Hey {name} your aesthetic is exactly the space grvty lives in. "
            "It's a pyramid inspired lamp, 3D printed as a single piece. Clean geometry, honest materials, nothing extra. "
            "I'd love to send you one if you're open to it. Check @grvty.std for the design."
        ),
        (
            "Hi {name}! Your eye for restraint in design is rare. "
            "grvty is a pyramid shaped lamp, 3D printed as one continuous piece. Same philosophy, nothing unnecessary. "
            "Would love to collaborate or send you one to see what you think."
        ),
    ],
    "industrialdesign": [
        (
            "Hey {name} as someone who thinks seriously about industrial design, "
            "I think you'd appreciate grvty. "
            "It's a pyramid inspired lamp, 3D printed as one single piece where the process is visible in the final form. "
            "Would love to send you one and hear your thoughts."
        ),
    ],
    "default": [
        (
            "Hey {name} love what you're putting out. "
            "I designed grvty, a 3D printed lamp inspired by the pyramid shape, all one piece. "
            "Think your audience would genuinely connect with it. Check @grvty.std and let me know!"
        ),
        (
            "Hi {name}! Your content is exactly the creative space I want grvty to be part of. "
            "It's a pyramid shaped 3D printed lamp, one single piece, the craft is real. "
            "Open to sending you one to check out, no obligation. Hope to connect!"
        ),
    ],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _detect_niches(tags: str, bio: str) -> list[str]:
    """Return matched niche keys from niche_tags + biography."""
    combined = (tags + " " + bio).lower()
    found = []
    priority = [
        "3dprinting", "lamp", "minimalism", "brutalism",
        "industrialdesign", "productdesign", "design"
    ]
    for niche in priority:
        # Match niche keyword loosely (e.g. "3dprint" matches "3dprinting")
        clean = niche.replace("design", "design").replace("3dprinting", "3dprint")
        if clean in combined or niche in combined:
            found.append(niche)
    return found or ["design"]


def suggest_comment(
    bio: str,
    niche_tags: str,
    post_caption: Optional[str] = None,
) -> str:
    niches = _detect_niches(niche_tags, bio)
    # Pick from the most specific matching niche
    for niche in niches:
        pool = COMMENT_TEMPLATES.get(niche, [])
        if pool:
            return random.choice(pool)
    return random.choice(COMMENT_TEMPLATES["design"])


def suggest_dm(
    username: str,
    full_name: Optional[str],
    bio: str,
    niche_tags: str,
) -> str:
    name = full_name.split()[0] if full_name else username
    niches = _detect_niches(niche_tags, bio)

    for niche in niches:
        pool = DM_TEMPLATES.get(niche, [])
        if pool:
            return random.choice(pool).format(name=name)

    return random.choice(DM_TEMPLATES["default"]).format(name=name)


def build_action_plan(creator: dict, posts: list[dict]) -> dict:
    """
    Given a creator dict and their top posts, return a full action plan:
    - profile link
    - best post link + comment suggestion for that post
    - DM suggestion
    """
    username    = creator.get("username", "")
    bio         = creator.get("biography") or ""
    niche_tags  = creator.get("niche_tags") or ""
    full_name   = creator.get("full_name") or ""

    # Pick best post (highest likes)
    best_post = max(posts, key=lambda p: p.get("like_count", 0)) if posts else None

    comment = suggest_comment(bio, niche_tags, best_post.get("caption") if best_post else None)
    dm      = suggest_dm(username, full_name, bio, niche_tags)

    return {
        "profile_url":   f"https://www.instagram.com/{username}/",
        "post_url":      best_post["permalink"] if best_post else None,
        "post_likes":    best_post.get("like_count", 0) if best_post else 0,
        "post_caption":  (best_post.get("caption") or "")[:120] if best_post else "",
        "comment":       comment,
        "dm":            dm,
        "matched_niches": _detect_niches(niche_tags, bio),
    }
