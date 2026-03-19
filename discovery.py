"""
Discovery module.

Workflow:
  1. Resolve each target hashtag to its Instagram ID
  2. Pull top + recent media for each hashtag
  3. Collect unique creator usernames from post owners
  4. Fetch full profiles via Business Discovery
  5. Score each creator by relevance + engagement
  6. Persist everything to SQLite
"""

import logging
import re
from typing import Optional
from api_client import InstagramClient, InstagramAPIError
from database import init_db, upsert_hashtag, upsert_creator, upsert_post, get_top_creators
from config import HASHTAGS, SCORING_WEIGHTS, MIN_FOLLOWERS, MAX_FOLLOWERS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _engagement_rate(followers: int, avg_likes: float, avg_comments: float) -> float:
    if followers == 0:
        return 0.0
    return (avg_likes + avg_comments) / followers


def _avg_interaction(media: list[dict], field: str) -> float:
    values = [m.get(field, 0) or 0 for m in media]
    return sum(values) / len(values) if values else 0.0


def score_creator(profile: dict, matched_hashtags: list[str]) -> float:
    """
    Returns a 0–100 relevance score.

    Factors (weights defined in config.py):
      - engagement_rate   : (likes+comments) / followers
      - follower_tier     : logarithmic — sweet spot 5k–200k
      - hashtag_overlap   : how many of our target hashtags they appear in
      - has_website       : small signal for brand/creator legitimacy
    """
    followers = profile.get("followers_count", 0) or 0
    media = (profile.get("media") or {}).get("data", [])

    avg_likes    = _avg_interaction(media, "like_count")
    avg_comments = _avg_interaction(media, "comments_count")
    er = _engagement_rate(followers, avg_likes, avg_comments)

    # Engagement score: ER of 3–8% = ideal for this niche
    er_score = min(er / 0.08, 1.0) * 100

    # Follower tier score (log scale, sweet spot ~50k)
    import math
    if followers > 0:
        # peaks at log(50000) ≈ 10.8
        follower_score = max(0, 100 - abs(math.log(followers) - math.log(50_000)) * 15)
    else:
        follower_score = 0

    # Hashtag overlap
    max_overlap = len(HASHTAGS)
    overlap_score = (len(matched_hashtags) / max_overlap) * 100 if max_overlap else 0

    # Website presence
    website_score = 50 if profile.get("website") else 0

    w = SCORING_WEIGHTS
    total = (
        w["engagement"]  * er_score     +
        w["followers"]   * follower_score +
        w["overlap"]     * overlap_score  +
        w["website"]     * website_score
    )
    return round(total, 2)


# ---------------------------------------------------------------------------
# Core discovery
# ---------------------------------------------------------------------------

class DiscoveryEngine:
    def __init__(self, client: InstagramClient):
        self.client = client
        self._hashtag_id_cache: dict[str, str] = {}

    def _resolve_hashtag(self, tag: str) -> Optional[str]:
        tag = tag.lstrip("#").lower()
        if tag in self._hashtag_id_cache:
            return self._hashtag_id_cache[tag]
        ht_id = self.client.get_hashtag_id(tag)
        if ht_id:
            self._hashtag_id_cache[tag] = ht_id
            upsert_hashtag(ht_id, tag)
            logger.info(f"Resolved #{tag} -> {ht_id}")
        else:
            logger.warning(f"Could not resolve #{tag}")
        return ht_id

    def discover_from_hashtag(
        self,
        hashtag: str,
        mode: str = "top",       # "top" | "recent" | "both"
        media_limit: int = 50,
    ) -> dict[str, list[str]]:
        """
        Pull media for a hashtag and return a mapping:
            { username: [hashtag, ...] }
        """
        ht_id = self._resolve_hashtag(hashtag)
        if not ht_id:
            return {}

        media_items: list[dict] = []
        tag_clean = hashtag.lstrip("#").lower()

        if mode in ("top", "both"):
            media_items += self.client.get_hashtag_top_media(ht_id, limit=media_limit)
        if mode in ("recent", "both"):
            media_items += self.client.get_hashtag_recent_media(ht_id, limit=media_limit)

        creator_map: dict[str, list[str]] = {}

        for post in media_items:
            caption = post.get("caption") or ""

            # Extract @mentions from caption as creator leads
            mentions = re.findall(r"@([A-Za-z0-9_.]+)", caption)

            # Also extract username from permalink if possible
            permalink = post.get("permalink", "")

            # Persist the post (use post id as creator_id placeholder)
            post_id = post.get("id", "")
            upsert_post({
                "id":            post_id,
                "creator_id":    post_id,  # no owner available from hashtag media
                "permalink":     permalink,
                "caption":       caption[:500],
                "media_type":    post.get("media_type", ""),
                "like_count":    post.get("like_count", 0),
                "comment_count": post.get("comments_count", 0),
                "timestamp":     post.get("timestamp", ""),
                "hashtag_source": tag_clean,
            })

            # Add each @mentioned user as a potential creator
            for username in mentions:
                username = username.lower().rstrip(".")
                if len(username) < 3:
                    continue
                if username not in creator_map:
                    creator_map[username] = []
                if tag_clean not in creator_map[username]:
                    creator_map[username].append(tag_clean)

        logger.info(f"#{tag_clean}: found {len(creator_map)} unique creators from {len(media_items)} posts")
        return creator_map

    def enrich_creators(self, creator_tag_map: dict[str, list[str]]) -> int:
        """
        Fetch full profiles for each creator and persist to DB.
        Returns count of successfully enriched creators.
        """
        enriched = 0

        for username, matched_tags in creator_tag_map.items():
            try:
                profile = self.client.get_creator_profile(username)
            except InstagramAPIError as e:
                logger.warning(f"Could not fetch @{username}: {e}")
                continue

            if not profile:
                logger.debug(f"@{username} returned no profile (private/not found)")
                continue

            followers = profile.get("followers_count", 0) or 0

            # Apply follower filter
            if followers < MIN_FOLLOWERS or followers > MAX_FOLLOWERS:
                logger.debug(f"@{username} filtered out (followers={followers})")
                continue

            media = (profile.get("media") or {}).get("data", [])
            avg_likes    = _avg_interaction(media, "like_count")
            avg_comments = _avg_interaction(media, "comments_count")
            er = _engagement_rate(followers, avg_likes, avg_comments)
            creator_score = score_creator(profile, matched_tags)

            upsert_creator({
                "id":              profile.get("id", username),
                "username":        profile.get("username", username),
                "full_name":       profile.get("name", ""),
                "biography":       (profile.get("biography") or "")[:500],
                "followers":       followers,
                "following":       profile.get("follows_count", 0),
                "post_count":      profile.get("media_count", 0),
                "avg_likes":       round(avg_likes, 2),
                "avg_comments":    round(avg_comments, 2),
                "engagement_rate": round(er * 100, 4),
                "account_type":    "",
                "website":         profile.get("website", ""),
                "niche_tags":      ",".join(matched_tags),
                "score":           creator_score,
            })

            enriched += 1
            logger.info(
                f"Saved @{username} | followers={followers:,} | "
                f"ER={er*100:.2f}% | score={creator_score}"
            )

        return enriched

    def run_full_discovery(
        self,
        hashtags: Optional[list[str]] = None,
        mode: str = "top",
        media_limit: int = 50,
    ) -> list[dict]:
        """
        Full pipeline: hashtag → posts → profiles → scored leads.
        Returns top creators sorted by score.
        """
        init_db()
        hashtags = hashtags or HASHTAGS
        combined_map: dict[str, list[str]] = {}

        # Seed with known niche creators for reliable baseline leads
        SEED_CREATORS = {
            # 3D printing
            "formlabs": ["3dprinting"],
            "creality.official": ["3dprinting"],
            "elegoo_official": ["3dprinting"],
            "bambulab_global": ["3dprinting"],
            "3d_printing_world": ["3dprinting"],
            "3dprintingnerd": ["3dprinting"],
            "makersworkshopofficial": ["3dprinting"],
            "thangs3d": ["3dprinting"],
            "myminifactory": ["3dprinting"],
            "printables_official": ["3dprinting"],
            # Design / architecture
            "dezeen": ["design", "industrialdesign", "brutalism"],
            "leibal": ["minimalism", "design"],
            "designmilk": ["design", "minimalism"],
            "designboom": ["design", "industrialdesign"],
            "archdaily": ["design", "brutalism"],
            "stfranciselectric": ["design", "lamp"],
            "minimalissimo": ["minimalism"],
            "thedsgnblog": ["design", "minimalism"],
            "industrialdesigners": ["industrialdesign", "productdesign"],
            # Lighting / lamps
            "ambientec_official": ["lamp", "design"],
            "foscarinilamps": ["lamp", "design"],
            "floslighting": ["lamp", "minimalism"],
            "artemaborig": ["lamp", "design"],
            "muaborig": ["lamp", "minimalism"],
            "taborig": ["lamp", "design"],
            # Brutalism / raw design
            "brutalhouse": ["brutalism", "design"],
            "brutgroup": ["brutalism"],
            "brutal_architecture": ["brutalism"],
        }
        combined_map.update(SEED_CREATORS)
        logger.info(f"Seeded {len(SEED_CREATORS)} known niche creators")

        for tag in hashtags:
            logger.info(f"Scanning #{tag} ...")
            partial = self.discover_from_hashtag(tag, mode=mode, media_limit=media_limit)
            for username, tags in partial.items():
                if username not in combined_map:
                    combined_map[username] = []
                for t in tags:
                    if t not in combined_map[username]:
                        combined_map[username].append(t)

        logger.info(f"Total unique creators found: {len(combined_map)}")
        logger.info("Enriching profiles via Business Discovery ...")
        enriched = self.enrich_creators(combined_map)
        logger.info(f"Enriched and saved {enriched} creators.")

        return get_top_creators(limit=100)
