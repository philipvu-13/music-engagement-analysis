# scripts/02_match_youtube_videos.py
import os
import re
from pathlib import Path

import pandas as pd
import requests
import isodate
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
IN_TRACKS = DATA_DIR / "tracks.csv"
OUT_VIDEOS = DATA_DIR / "youtube_videos.csv"

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

# Your known official channel (handle -> channelId lookup is fine too)
CHANNEL_ID = "UC0KAFLxIiaR_FFNYDL3utGw"

ALBUM_TITLE = "Don't Be Dumb"

# If you manually grab the Releases playlist ID (recommended), put it here.
# It often looks like OLAK5uy...
ALBUM_PLAYLIST_ID = "OLAK5uy_lW4LAXRvQ_YHM7eNelKA0uAYUcpgL1b8g"


def normalize(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("’", "'")
    s = re.sub(r"[^a-z0-9\s']", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def duration_seconds(iso):
    try:
        return int(isodate.parse_duration(iso).total_seconds())
    except Exception:
        return None


def yt_search_album_playlist(api_key: str, channel_id: str, album_title: str) -> str:
    """
    Searches playlists on the channel for the album title and returns the best playlistId.
    """
    r = requests.get(
        f"{YOUTUBE_API_BASE}/search",
        params={
            "key": api_key,
            "part": "snippet",
            "channelId": channel_id,
            "q": album_title,
            "type": "playlist",
            "maxResults": 10,
        },
        timeout=30,
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        raise RuntimeError("No playlist search results found for album title on this channel.")

    # Prefer playlists whose title is closest to album title and/or OLAK5uy style IDs
    album_n = normalize(album_title)

    def score(item):
        pid = item["id"]["playlistId"]
        title = item["snippet"].get("title", "")
        title_n = normalize(title)

        s = 0
        if album_n in title_n:
            s += 50
        # Many official "album" playlists are OLAK5uy...
        if pid.startswith("OLAK5uy"):
            s += 30
        # Minor bonus if "album" or "release" appears
        if "album" in title_n or "release" in title_n:
            s += 10
        return s

    best = max(items, key=score)
    return best["id"]["playlistId"]


def yt_get_all_playlist_videos(api_key: str, playlist_id: str):
    """
    Returns list of {video_id, title, published_at}
    """
    videos = []
    page_token = None

    while True:
        r = requests.get(
            f"{YOUTUBE_API_BASE}/playlistItems",
            params={
                "key": api_key,
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": 50,
                "pageToken": page_token,
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()

        for item in data.get("items", []):
            vid = item["contentDetails"]["videoId"]
            title = item["snippet"].get("title", "")
            published_at = item["snippet"].get("publishedAt", "")
            videos.append({"video_id": vid, "title": title, "published_at": published_at})

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return videos


def yt_get_video_durations(api_key: str, video_ids):
    durations = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        r = requests.get(
            f"{YOUTUBE_API_BASE}/videos",
            params={
                "key": api_key,
                "part": "contentDetails",
                "id": ",".join(batch),
            },
            timeout=30,
        )
        r.raise_for_status()
        for it in r.json().get("items", []):
            durations[it["id"]] = duration_seconds(it["contentDetails"].get("duration"))
    return durations


def main():
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing YOUTUBE_API_KEY in .env")

    tracks = pd.read_csv(IN_TRACKS)

    playlist_id = ALBUM_PLAYLIST_ID
    if not playlist_id:
        playlist_id = yt_search_album_playlist(api_key, CHANNEL_ID, ALBUM_TITLE)

    print(f"Using album playlist: {playlist_id}")

    album_videos = yt_get_all_playlist_videos(api_key, playlist_id)
    video_ids = [v["video_id"] for v in album_videos]
    durations = yt_get_video_durations(api_key, video_ids)

    # Map tracks -> one best video from this album playlist
    rows = []
    for _, t in tracks.sort_values("track_number").iterrows():
        track_norm = normalize(t["track_name"])

        # Find first playlist video whose title contains the track name and is long enough
        chosen = None
        for v in album_videos:
            title_norm = normalize(v["title"])
            if track_norm in title_norm:
                if (durations.get(v["video_id"]) or 0) >= 30:  # audio tracks can be short-ish
                    chosen = v
                    break

        rows.append(
            {
                "track_id": t["track_id"],
                "youtube_video_id": chosen["video_id"] if chosen else None,
                "youtube_title": chosen["title"] if chosen else None,
                "channel_title": "A$AP Rocky (Releases)",
                "published_at": chosen["published_at"] if chosen else None,
                "is_official": True,
                "match_confidence": "high" if chosen else "none",
            }
        )

        print(f'{t["track_number"]:02d} {t["track_name"]} -> {chosen["video_id"] if chosen else "NO MATCH"}')

    pd.DataFrame(rows).to_csv(OUT_VIDEOS, index=False)
    print(f"Wrote {OUT_VIDEOS}")


if __name__ == "__main__":
    main()
