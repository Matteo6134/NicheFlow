"""
SQLite database layer for storing discovered creators and posts.
Schema:
  - creators  : potential outreach targets
  - posts     : individual posts that triggered discovery
  - hashtags  : tracked hashtag metadata
"""

import sqlite3
import contextlib
from datetime import datetime
from pathlib import Path
from typing import Optional


DB_PATH = Path(__file__).parent / "leads.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextlib.contextmanager
def get_db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS hashtags (
                id          TEXT PRIMARY KEY,   -- Instagram hashtag id
                name        TEXT NOT NULL,
                media_count INTEGER,
                last_synced TEXT
            );

            CREATE TABLE IF NOT EXISTS creators (
                id              TEXT PRIMARY KEY,   -- Instagram user id
                username        TEXT NOT NULL,
                full_name       TEXT,
                biography       TEXT,
                followers       INTEGER,
                following       INTEGER,
                post_count      INTEGER,
                avg_likes       REAL,
                avg_comments    REAL,
                engagement_rate REAL,               -- (likes+comments)/followers
                account_type    TEXT,               -- BUSINESS / CREATOR / PERSONAL
                website         TEXT,
                niche_tags      TEXT,               -- comma-separated matched hashtags
                score           REAL DEFAULT 0,     -- calculated relevance score
                status          TEXT DEFAULT 'new', -- new | reviewed | contacted | skip
                notes           TEXT,
                discovered_at   TEXT NOT NULL,
                updated_at      TEXT
            );

            CREATE TABLE IF NOT EXISTS posts (
                id              TEXT PRIMARY KEY,   -- Instagram media id
                creator_id      TEXT NOT NULL,
                permalink       TEXT,
                caption         TEXT,
                media_type      TEXT,
                like_count      INTEGER,
                comment_count   INTEGER,
                timestamp       TEXT,
                hashtag_source  TEXT,               -- which hashtag triggered discovery
                discovered_at   TEXT NOT NULL,
                FOREIGN KEY(creator_id) REFERENCES creators(id)
            );

            CREATE TABLE IF NOT EXISTS daily_queue (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                date         TEXT NOT NULL,           -- YYYY-MM-DD
                creator_id   TEXT NOT NULL,
                status       TEXT DEFAULT 'pending',  -- pending | done | skipped
                contacted_at TEXT,
                UNIQUE(date, creator_id),
                FOREIGN KEY(creator_id) REFERENCES creators(id)
            );

            CREATE INDEX IF NOT EXISTS idx_creators_score   ON creators(score DESC);
            CREATE INDEX IF NOT EXISTS idx_creators_status  ON creators(status);
            CREATE INDEX IF NOT EXISTS idx_posts_creator    ON posts(creator_id);
            CREATE INDEX IF NOT EXISTS idx_queue_date       ON daily_queue(date);
        """)


# ---------------------------------------------------------------------------
# Hashtag helpers
# ---------------------------------------------------------------------------

def upsert_hashtag(id_: str, name: str, media_count: Optional[int] = None) -> None:
    with get_db() as db:
        db.execute("""
            INSERT INTO hashtags (id, name, media_count, last_synced)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                media_count = excluded.media_count,
                last_synced = excluded.last_synced
        """, (id_, name, media_count, datetime.utcnow().isoformat()))


# ---------------------------------------------------------------------------
# Creator helpers
# ---------------------------------------------------------------------------

def upsert_creator(data: dict) -> None:
    now = datetime.utcnow().isoformat()
    with get_db() as db:
        db.execute("""
            INSERT INTO creators (
                id, username, full_name, biography,
                followers, following, post_count,
                avg_likes, avg_comments, engagement_rate,
                account_type, website, niche_tags, score,
                status, discovered_at, updated_at
            ) VALUES (
                :id, :username, :full_name, :biography,
                :followers, :following, :post_count,
                :avg_likes, :avg_comments, :engagement_rate,
                :account_type, :website, :niche_tags, :score,
                'new', :now, :now
            )
            ON CONFLICT(id) DO UPDATE SET
                username        = excluded.username,
                full_name       = excluded.full_name,
                followers       = excluded.followers,
                following       = excluded.following,
                post_count      = excluded.post_count,
                avg_likes       = excluded.avg_likes,
                avg_comments    = excluded.avg_comments,
                engagement_rate = excluded.engagement_rate,
                niche_tags      = excluded.niche_tags,
                score           = excluded.score,
                updated_at      = excluded.updated_at
            WHERE creators.status = 'new'
        """, {**data, "now": now})


def upsert_post(data: dict) -> None:
    now = datetime.utcnow().isoformat()
    with get_db() as db:
        db.execute("""
            INSERT OR IGNORE INTO posts (
                id, creator_id, permalink, caption,
                media_type, like_count, comment_count,
                timestamp, hashtag_source, discovered_at
            ) VALUES (
                :id, :creator_id, :permalink, :caption,
                :media_type, :like_count, :comment_count,
                :timestamp, :hashtag_source, :now
            )
        """, {**data, "now": now})


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def query_creators(
    status: str = "",
    niche: str = "",
    sort_by: str = "score",
    order: str = "desc",
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Filtered, sorted, paginated creator query. Returns (items, total_count)."""
    clauses = []
    params: list = []

    if status:
        clauses.append("status = ?")
        params.append(status)
    else:
        clauses.append("status != 'skip'")

    if niche:
        clauses.append("niche_tags LIKE ?")
        params.append(f"%{niche}%")

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    order_sql = f"ORDER BY {sort_by} {order.upper()}"

    with get_db() as db:
        total = db.execute(
            f"SELECT COUNT(*) FROM creators {where}", params
        ).fetchone()[0]
        rows = db.execute(
            f"SELECT * FROM creators {where} {order_sql} LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

    return [dict(r) for r in rows], total


def get_top_creators(limit: int = 50, min_score: float = 0.0) -> list[dict]:
    with get_db() as db:
        rows = db.execute("""
            SELECT * FROM creators
            WHERE score >= ? AND status != 'skip'
            ORDER BY score DESC
            LIMIT ?
        """, (min_score, limit)).fetchall()
    return [dict(r) for r in rows]


def get_creators_by_status(status: str) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM creators WHERE status = ? ORDER BY score DESC",
            (status,)
        ).fetchall()
    return [dict(r) for r in rows]


def update_creator_status(creator_id: str, status: str, notes: str = "") -> None:
    with get_db() as db:
        db.execute(
            "UPDATE creators SET status = ?, notes = ?, updated_at = ? WHERE id = ?",
            (status, notes, datetime.utcnow().isoformat(), creator_id)
        )


# ---------------------------------------------------------------------------
# Daily queue helpers
# ---------------------------------------------------------------------------

def get_queue_for_date(date: str) -> list[dict]:
    """Return all queue entries for a given YYYY-MM-DD date with creator data joined."""
    with get_db() as db:
        rows = db.execute("""
            SELECT dq.id as queue_id, dq.status as queue_status, dq.contacted_at,
                   c.*
            FROM daily_queue dq
            JOIN creators c ON c.id = dq.creator_id
            WHERE dq.date = ?
            ORDER BY c.score DESC
        """, (date,)).fetchall()
    return [dict(r) for r in rows]


def fill_queue_for_date(date: str, size: int = 10) -> None:
    """
    Populate today's queue with `size` top-scored creators
    that haven't been queued or contacted before.
    """
    with get_db() as db:
        already = db.execute(
            "SELECT creator_id FROM daily_queue WHERE date = ?", (date,)
        ).fetchall()
        already_ids = {r["creator_id"] for r in already}

        ever_queued = db.execute(
            "SELECT DISTINCT creator_id FROM daily_queue"
        ).fetchall()
        ever_ids = {r["creator_id"] for r in ever_queued}

        candidates = db.execute("""
            SELECT id FROM creators
            WHERE status NOT IN ('skip', 'contacted')
            ORDER BY score DESC
            LIMIT 200
        """).fetchall()

        picks = [r["id"] for r in candidates if r["id"] not in ever_ids][:size]

        # If not enough fresh ones, backfill with oldest-contacted
        if len(picks) < size:
            backfill = db.execute("""
                SELECT creator_id FROM daily_queue
                WHERE status = 'done'
                GROUP BY creator_id
                ORDER BY MAX(contacted_at) ASC
                LIMIT ?
            """, (size - len(picks),)).fetchall()
            picks += [r["creator_id"] for r in backfill if r["creator_id"] not in already_ids]

        for cid in picks:
            db.execute(
                "INSERT OR IGNORE INTO daily_queue (date, creator_id) VALUES (?, ?)",
                (date, cid)
            )


def get_posts_for_creator(creator_id: str, limit: int = 3) -> list[dict]:
    with get_db() as db:
        rows = db.execute("""
            SELECT id, permalink, caption, like_count, comment_count, media_type
            FROM posts WHERE creator_id = ?
            ORDER BY like_count DESC LIMIT ?
        """, (creator_id, limit)).fetchall()
    return [dict(r) for r in rows]


def mark_queue_item(queue_id: int, status: str) -> None:
    with get_db() as db:
        db.execute(
            "UPDATE daily_queue SET status = ?, contacted_at = ? WHERE id = ?",
            (status, datetime.utcnow().isoformat(), queue_id)
        )


def get_queue_stats() -> dict:
    with get_db() as db:
        total_contacted = db.execute(
            "SELECT COUNT(*) FROM daily_queue WHERE status = 'done'"
        ).fetchone()[0]
        streak_days = db.execute("""
            SELECT COUNT(DISTINCT date) FROM daily_queue
            WHERE status = 'done'
              AND date >= date('now', '-30 days')
        """).fetchone()[0]
        today = db.execute(
            "SELECT COUNT(*) FROM daily_queue WHERE date = date('now') AND status = 'done'"
        ).fetchone()[0]
        total_today = db.execute(
            "SELECT COUNT(*) FROM daily_queue WHERE date = date('now')"
        ).fetchone()[0]
    return {
        "total_contacted": total_contacted,
        "streak_days": streak_days,
        "today_done": today,
        "today_total": total_today,
    }


def export_to_csv(path: str = "leads_export.csv") -> str:
    """Export the full creators table to CSV for manual review."""
    import csv
    creators = get_top_creators(limit=10_000)
    if not creators:
        return "No creators found."
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=creators[0].keys())
        writer.writeheader()
        writer.writerows(creators)
    return path
