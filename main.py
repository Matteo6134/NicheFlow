"""
Entry point for the Instagram Discovery Tool.

Usage:
    python main.py                      # full discovery run
    python main.py --export             # export leads to CSV
    python main.py --top 20             # print top 20 leads
    python main.py --tag 3dprinting     # scan a single hashtag
    python main.py --status new         # list leads by status
"""

import argparse
import logging
import sys
from config import ACCESS_TOKEN, IG_USER_ID, HASHTAGS, DISCOVERY_MODE, MEDIA_PER_TAG
from api_client import InstagramClient
from discovery import DiscoveryEngine
from database import init_db, get_top_creators, get_creators_by_status, export_to_csv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _print_table(creators: list[dict]) -> None:
    if not creators:
        print("No creators found.")
        return
    header = f"{'#':<4} {'Username':<25} {'Followers':>10} {'ER%':>7} {'Score':>7}  Niches"
    print(header)
    print("-" * len(header))
    for i, c in enumerate(creators, 1):
        print(
            f"{i:<4} @{c['username']:<24} "
            f"{(c['followers'] or 0):>10,} "
            f"{(c['engagement_rate'] or 0):>7.2f} "
            f"{(c['score'] or 0):>7.1f}  "
            f"{c.get('niche_tags','')}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Instagram Discovery Tool")
    parser.add_argument("--export",  action="store_true",  help="Export leads to CSV")
    parser.add_argument("--top",     type=int, default=0,  help="Print top N leads")
    parser.add_argument("--tag",     type=str, default="", help="Scan a single hashtag")
    parser.add_argument("--status",  type=str, default="", help="Filter leads by status")
    parser.add_argument("--mode",    type=str, default=DISCOVERY_MODE,
                        choices=["top", "recent", "both"],
                        help="Media pull mode (default: top)")
    parser.add_argument("--limit",   type=int, default=MEDIA_PER_TAG,
                        help="Posts to pull per hashtag")
    args = parser.parse_args()

    # Validate credentials
    if ACCESS_TOKEN == "YOUR_LONG_LIVED_ACCESS_TOKEN":
        logger.error("Please set ACCESS_TOKEN and IG_USER_ID in config.py first.")
        sys.exit(1)

    init_db()
    client = InstagramClient(ACCESS_TOKEN, IG_USER_ID)
    engine = DiscoveryEngine(client)

    # --- Export mode ---
    if args.export:
        path = export_to_csv()
        print(f"Exported to: {path}")
        return

    # --- Status filter ---
    if args.status:
        creators = get_creators_by_status(args.status)
        print(f"\nLeads with status='{args.status}' ({len(creators)} found):\n")
        _print_table(creators)
        return

    # --- Quick top-N view ---
    if args.top:
        creators = get_top_creators(limit=args.top)
        print(f"\nTop {args.top} leads:\n")
        _print_table(creators)
        return

    # --- Single hashtag scan ---
    if args.tag:
        logger.info(f"Single-tag scan: #{args.tag}")
        creator_map = engine.discover_from_hashtag(
            args.tag, mode=args.mode, media_limit=args.limit
        )
        enriched = engine.enrich_creators(creator_map)
        print(f"\nEnriched {enriched} creators from #{args.tag}")
        _print_table(get_top_creators(limit=20))
        return

    # --- Full discovery run ---
    logger.info(f"Starting full discovery across {len(HASHTAGS)} hashtags ...")
    status = client.rate_status()
    logger.info(f"API quota: {status['calls_remaining']} calls remaining this hour")

    top_creators = engine.run_full_discovery(mode=args.mode, media_limit=args.limit)

    print(f"\n{'='*60}")
    print(f"Discovery complete — top {min(30, len(top_creators))} leads:")
    print(f"{'='*60}\n")
    _print_table(top_creators[:30])

    print(f"\nAll leads saved to: leads.db")
    print(f"Run with --export to get a CSV, or --top N to view more.")


if __name__ == "__main__":
    main()
