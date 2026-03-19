"""
Thin wrapper around the Instagram Graph API.
Only uses official, documented endpoints.
Docs: https://developers.facebook.com/docs/instagram-api
"""

import requests
from typing import Optional
from rate_limiter import RateLimiter


BASE_URL = "https://graph.facebook.com/v19.0"


class InstagramAPIError(Exception):
    def __init__(self, code: int, message: str, subcode: int = 0):
        self.code = code
        self.subcode = subcode
        super().__init__(f"[{code}/{subcode}] {message}")


class InstagramClient:
    def __init__(self, access_token: str, ig_user_id: str):
        self.token = access_token
        self.user_id = ig_user_id
        self.limiter = RateLimiter()
        self.session = requests.Session()
        self.session.params = {"access_token": self.access_token}  # type: ignore

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def access_token(self) -> str:
        return self.token

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        self.limiter.wait()
        url = f"{BASE_URL}/{path.lstrip('/')}"
        r = self.session.get(url, params=params or {})
        data = r.json()
        if "error" in data:
            err = data["error"]
            raise InstagramAPIError(
                err.get("code", 0),
                err.get("message", "Unknown error"),
                err.get("error_subcode", 0),
            )
        return data

    def _paginate(self, path: str, params: dict, max_items: int = 100) -> list[dict]:
        """Follow cursor-based pagination and collect up to max_items results."""
        results = []
        next_url: Optional[str] = None

        while len(results) < max_items:
            if next_url:
                self.limiter.wait()
                r = self.session.get(next_url)
                data = r.json()
            else:
                data = self._get(path, params)

            items = data.get("data", [])
            results.extend(items)

            paging = data.get("paging", {})
            next_url = paging.get("next")
            if not next_url:
                break

        return results[:max_items]

    # ------------------------------------------------------------------
    # Hashtag endpoints
    # ------------------------------------------------------------------

    def get_hashtag_id(self, hashtag_name: str) -> Optional[str]:
        """
        GET /ig_hashtag_search
        Returns the internal Instagram ID for a hashtag name.
        """
        data = self._get("ig_hashtag_search", {
            "user_id": self.user_id,
            "q": hashtag_name.lstrip("#"),
        })
        ids = data.get("data", [])
        return ids[0]["id"] if ids else None

    def get_hashtag_top_media(self, hashtag_id: str, limit: int = 50) -> list[dict]:
        """
        GET /{hashtag-id}/top_media
        Returns top (highest-engagement) recent media for a hashtag.
        """
        return self._paginate(
            f"{hashtag_id}/top_media",
            {
                "user_id": self.user_id,
                "fields": "id,timestamp,like_count,comments_count,media_type,"
                          "permalink,caption",
                "limit": min(limit, 50),
            },
            max_items=limit,
        )

    def get_hashtag_recent_media(self, hashtag_id: str, limit: int = 50) -> list[dict]:
        """
        GET /{hashtag-id}/recent_media
        Returns recent media for a hashtag (chronological).
        """
        return self._paginate(
            f"{hashtag_id}/recent_media",
            {
                "user_id": self.user_id,
                "fields": "id,timestamp,like_count,comments_count,media_type,"
                          "permalink,caption",
                "limit": min(limit, 50),
            },
            max_items=limit,
        )

    # ------------------------------------------------------------------
    # Business Discovery endpoint
    # ------------------------------------------------------------------

    def get_creator_profile(self, username: str) -> Optional[dict]:
        """
        GET /{ig-user-id}?fields=business_discovery.username(TARGET){fields...}
        Retrieve public profile data for any public Instagram account.
        Requires the calling account to be a Business or Creator account.
        """
        fields = (
            f"business_discovery.username({username})"
            "{id,username,name,biography,followers_count,follows_count,"
            "media_count,profile_picture_url,website,"
            "media{like_count,comments_count,timestamp,media_type}}"
        )
        try:
            data = self._get(self.user_id, {"fields": fields})
            return data.get("business_discovery")
        except InstagramAPIError as e:
            # code 100 = param error / not found; code 110 = invalid user
            if e.code in (100, 110):
                return None
            raise

    # ------------------------------------------------------------------
    # Own account
    # ------------------------------------------------------------------

    def get_my_profile(self) -> dict:
        return self._get(self.user_id, {
            "fields": "id,username,biography,followers_count,"
                      "follows_count,media_count,website"
        })

    def rate_status(self) -> dict:
        return {
            "calls_this_hour": self.limiter.calls_this_hour,
            "calls_remaining": self.limiter.calls_remaining,
        }
