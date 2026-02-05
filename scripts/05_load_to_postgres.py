"""
05_load_to_postgres.py

One-time loader:
- Clears tables
- Loads CSVs into Postgres using COPY (fast)

Requirements:
  python -m pip install psycopg2-binary python-dotenv

Optional .env (project root):
  POSTGRES_HOST=localhost
  POSTGRES_PORT=5432
  POSTGRES_DB=dont_be_dumb
  POSTGRES_USER=postgres
  POSTGRES_PASSWORD=postgres
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import psycopg2


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

FILES = {
    "tracks": DATA_DIR / "tracks.csv",
    "lyrics": DATA_DIR / "lyrics.csv",
    "youtube_videos": DATA_DIR / "youtube_videos.csv",
    "youtube_stats_snapshots": DATA_DIR / "youtube_stats_snapshots.csv",
}


def get_conn():
    load_dotenv(PROJECT_ROOT / ".env")
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "dont_be_dumb"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )


def assert_files():
    missing = [str(p) for p in FILES.values() if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing CSV file(s):\n" + "\n".join(missing))


def copy_csv(cur, table: str, path: Path):
    with open(path, "r", encoding="utf-8") as f:
        cur.copy_expert(
            f"COPY public.{table} FROM STDIN WITH (FORMAT csv, HEADER true)",
            f,
        )


def main():
    assert_files()

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                # Clear existing rows
                cur.execute("""
                    TRUNCATE TABLE
                        public.youtube_stats_snapshots,
                        public.youtube_videos,
                        public.lyrics,
                        public.tracks
                    RESTART IDENTITY CASCADE;
                """)

                # Load in correct order
                copy_csv(cur, "tracks", FILES["tracks"])
                copy_csv(cur, "lyrics", FILES["lyrics"])
                copy_csv(cur, "youtube_videos", FILES["youtube_videos"])
                copy_csv(cur, "youtube_stats_snapshots", FILES["youtube_stats_snapshots"])

                # Print counts
                cur.execute("""
                    SELECT
                      (SELECT COUNT(*) FROM public.tracks),
                      (SELECT COUNT(*) FROM public.lyrics),
                      (SELECT COUNT(*) FROM public.youtube_videos),
                      (SELECT COUNT(*) FROM public.youtube_stats_snapshots);
                """)
                tracks, lyrics, videos, snaps = cur.fetchone()

                print("✅ Loaded successfully")
                print(f"tracks: {tracks}")
                print(f"lyrics: {lyrics}")
                print(f"youtube_videos: {videos}")
                print(f"youtube_stats_snapshots: {snaps}")

    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Load failed: {e}", file=sys.stderr)
        sys.exit(1)
