"""
03_pull_youtube_stats.py

Purpose:
- Pull current YouTube engagement stats (views, likes, comments)
- Record them as time-stamped snapshots in UTC
- Append snapshots over time for growth analysis

Run daily (or every few days). Uses UTC consistently.
"""

import os
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import requests
from dotenv import load_dotenv


FORCE_RUN = False  # set to False after testing


# -----------------------------
# Config
# -----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

IN_VIDEOS = DATA_DIR / "youtube_videos.csv"
OUT_STATS = DATA_DIR / "youtube_stats_snapshots.csv"

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

# Evening snapshot window in UTC
EVENING_START_UTC = 18  # 18:00 UTC
EVENING_END_UTC = 22    # 22:00 UTC


# -----------------------------
# Helpers
# -----------------------------
def yt_get_video_stats(api_key: str, video_ids: list[str]) -> dict:
    """
    Fetch statistics for up to 50 videos at a time.
    Returns: { video_id: {view_count, like_count, comment_count} }
    """
    stats = {}

    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]

        r = requests.get(
            f"{YOUTUBE_API_BASE}/videos",
            params={
                "key": api_key,
                "part": "statistics",
                "id": ",".join(batch),
            },
            timeout=30,
        )
        r.raise_for_status()

        for item in r.json().get("items", []):
            vid = item["id"]
            s = item.get("statistics", {})

            stats[vid] = {
                "view_count": int(s.get("viewCount", 0)),
                "like_count": int(s.get("likeCount", 0)) if "likeCount" in s else None,
                "comment_count": int(s.get("commentCount", 0)) if "commentCount" in s else None,
            }

    return stats


# -----------------------------
# Main
# -----------------------------
def main():
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("YOUTUBE_API_KEY")

    if not api_key:
        raise RuntimeError("Missing YOUTUBE_API_KEY in .env")

    if not IN_VIDEOS.exists():
        raise FileNotFoundError(
            "youtube_videos.csv not found. Run 02_match_youtube_videos.py first."
        )

    # Enforce consistent UTC snapshot window
    now_utc = datetime.now(timezone.utc)
    current_hour = now_utc.hour

    if not FORCE_RUN:
        if not (EVENING_START_UTC <= current_hour < EVENING_END_UTC):
            print(
                f"[SKIP] Current UTC hour is {current_hour}. "
                f"Snapshots only collected between "
                f"{EVENING_START_UTC}:00–{EVENING_END_UTC}:00 UTC."
            )
            return
    else:
        print("[TEST MODE] FORCE_RUN is True; skipping time window check.")
    
    videos_df = pd.read_csv(IN_VIDEOS)

    video_ids = (
        videos_df["youtube_video_id"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    if not video_ids:
        raise RuntimeError("No valid YouTube video IDs found.")

    stats_map = yt_get_video_stats(api_key, video_ids)

    rows = []
    for vid in video_ids:
        s = stats_map.get(vid)
        if not s:
            continue

        rows.append(
            {
                "youtube_video_id": vid,
                "captured_at": now_utc.isoformat(),
                "view_count": s["view_count"],
                "like_count": s["like_count"],
                "comment_count": s["comment_count"],
            }
        )

    snapshot_df = pd.DataFrame(rows)

    if snapshot_df.empty:
        print("[WARN] No stats returned from API.")
        return

    # Append snapshots (never overwrite)
    if OUT_STATS.exists():
        snapshot_df.to_csv(OUT_STATS, mode="a", header=False, index=False)
    else:
        snapshot_df.to_csv(OUT_STATS, index=False)

    print(
        f"[OK] Captured stats for {len(snapshot_df)} videos "
        f"at {now_utc.isoformat()} UTC"
    )
    print(f"[OK] Saved to {OUT_STATS}")


if __name__ == "__main__":
    main()
