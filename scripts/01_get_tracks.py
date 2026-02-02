import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os


# -----------------------------
# Config
# -----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

OUT_TRACKS = DATA_DIR / "tracks.csv"

# You set these to your album/artist:
ALBUM_NAME = "Don't Be Dumb"
ARTIST_NAME = "A$AP Rocky"

# Stable prefix for IDs in your database
ALBUM_SLUG = "dont_be_dumb"

GENIUS_API_BASE = "https://api.genius.com"


# -----------------------------
# Helpers: cleaning & IDs
# -----------------------------
def clean_track_name(name: str) -> str:
    if name is None:
        return ""
    s = str(name).strip()
    s = re.sub(r"\s+", " ", s)

    # Remove (feat...) / [feat...]
    s = re.sub(r"[\(\[].*?(feat\.|ft\.|featuring).*?[\)\]]", "", s, flags=re.IGNORECASE)

    # Remove common noise in brackets
    s = re.sub(
        r"[\(\[].*?(official audio|official video|audio|video|explicit|clean|lyric[s]?).*?[\)\]]",
        "",
        s,
        flags=re.IGNORECASE,
    )

    # Remove trailing "- Official Audio" style suffix
    s = re.sub(r"\s*-\s*(official audio|official video|audio|video|lyrics?)\s*$", "", s, flags=re.IGNORECASE)

    # Remove trailing "Lyrics 123.4K" or "Lyrics 12K"
    s = re.sub(r"\s*lyrics\s*\d+(\.\d+)?k\s*$", "", s, flags=re.IGNORECASE)

    return re.sub(r"\s+", " ", s).strip()


def make_track_id(album_slug: str, track_number: int) -> str:
    return f"{album_slug}_{track_number:02d}"


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


# -----------------------------
# Genius API calls
# -----------------------------
def genius_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def genius_search(token: str, q: str, per_page: int = 10) -> List[dict]:
    r = requests.get(
        f"{GENIUS_API_BASE}/search",
        headers=genius_headers(token),
        params={"q": q},
        timeout=30,
    )
    r.raise_for_status()
    hits = r.json().get("response", {}).get("hits", [])
    return hits[:per_page]


def genius_song(token: str, song_id: int) -> dict:
    r = requests.get(
        f"{GENIUS_API_BASE}/songs/{song_id}",
        headers=genius_headers(token),
        params={"text_format": "plain"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("response", {}).get("song", {})


def pick_candidate_song_id(token: str, album_name: str, artist_name: str) -> Optional[int]:
    """
    Genius search returns SONG hits (not albums).
    We pick a likely song hit for this album/artist, then use /songs/:id to discover its album URL.
    """
    query = f"{album_name} {artist_name}"
    hits = genius_search(token, query, per_page=15)

    # Prefer hits where the primary artist matches
    artist_norm = normalize(artist_name)
    for h in hits:
        result = h.get("result", {})
        primary_artist = normalize(result.get("primary_artist", {}).get("name", ""))
        if artist_norm in primary_artist or primary_artist in artist_norm:
            song_id = result.get("id")
            if song_id:
                return int(song_id)

    # Fallback: first hit with an id
    for h in hits:
        song_id = h.get("result", {}).get("id")
        if song_id:
            return int(song_id)

    return None


# -----------------------------
# Scrape album page for tracklist
# -----------------------------
def extract_preloaded_state_json(html: str) -> Optional[dict]:
    """
    Genius pages often embed a large JSON state blob in a <script> tag (window.__PRELOADED_STATE__).
    This function tries to locate and decode it.
    """
    # Common pattern: window.__PRELOADED_STATE__ = JSON.parse("...escaped json...");
    m = re.search(r"window\.__PRELOADED_STATE__\s*=\s*JSON\.parse\(\"(.+?)\"\);", html)
    if not m:
        return None

    raw = m.group(1)

    # Unescape the JSON string content
    # It contains escaped quotes and unicode sequences.
    try:
        unescaped = raw.encode("utf-8").decode("unicode_escape")
        # Fix escaped slashes
        unescaped = unescaped.replace(r"\/", "/")
        return json.loads(unescaped)
    except Exception:
        return None


def find_tracks_in_state(state: dict, expected_album_name: str) -> Optional[List[Tuple[int, str]]]:
    """
    The structure can vary. We try to locate album/tracklist information in the preloaded state.
    Returns list of (track_number, track_title).
    """
    # Heuristic: search for any dicts containing "tracklist" or track-like objects.
    # We'll do a broad walk and collect anything that looks like track entries.
    expected = normalize(expected_album_name)
    candidates: List[Tuple[int, str]] = []

    def walk(x):
        if isinstance(x, dict):
            # Some states include album objects with name/title and tracklist items
            # We'll look for patterns:
            # - keys like "tracks", "tracklist", "track_number", "number"
            # - nested objects with "title" / "name"
            if "track_number" in x and ("title" in x or "name" in x):
                tn = x.get("track_number")
                title = x.get("title") or x.get("name")
                if isinstance(tn, int) and isinstance(title, str):
                    candidates.append((tn, title))

            if "number" in x and ("title" in x or "name" in x):
                tn = x.get("number")
                title = x.get("title") or x.get("name")
                if isinstance(tn, int) and isinstance(title, str):
                    candidates.append((tn, title))

            # Walk children
            for v in x.values():
                walk(v)

        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(state)

    # Deduplicate and sanity filter: track numbers should be positive and not insane
    cleaned = {}
    for tn, title in candidates:
        if 1 <= tn <= 50:
            # keep first seen
            cleaned.setdefault(tn, title)

    if not cleaned:
        return None

    # Return sorted
    return sorted(cleaned.items(), key=lambda t: t[0])


def scrape_album_tracklist(album_url: str, expected_album_name: str) -> List[Tuple[int, str]]:
    """
    Fetches the album page and tries to parse tracklist.
    Primary method: parse preloaded state JSON.
    Fallback: parse visible HTML tracklist rows (less reliable).
    """
    r = requests.get(album_url, timeout=30)
    r.raise_for_status()
    html = r.text

    # Method 1: preloaded state JSON
    state = extract_preloaded_state_json(html)
    if state:
        tracks = find_tracks_in_state(state, expected_album_name)
        if tracks:
            return tracks

    # Method 2: fallback HTML parsing (best-effort)
    soup = BeautifulSoup(html, "html.parser")

    # Genius album pages often have track rows with track numbers/titles visible.
    # We'll try multiple selectors.
    possible_rows = soup.select("[data-lyrics-container]")  # unlikely for album page, but harmless
    _ = possible_rows  # no-op

    # Another common pattern: chart rows or track listing elements
    rows = soup.select(".chart_row") or soup.select(".track_listing-track") or soup.select("[class*='Tracklist'] li")

    tracks: List[Tuple[int, str]] = []
    for row in rows:
        text = row.get_text(" ", strip=True)
        # Try to parse "1. Track Title"
        m = re.match(r"^(\d+)\.?\s+(.*)$", text)
        if m:
            tn = int(m.group(1))
            title = m.group(2)
            if 1 <= tn <= 50 and title:
                tracks.append((tn, title))

    # Dedup
    dedup = {}
    for tn, title in tracks:
        dedup.setdefault(tn, title)

    if dedup:
        return sorted(dedup.items(), key=lambda t: t[0])

    raise RuntimeError(
        "Could not extract tracklist from album page. Genius page structure may have changed."
    )


# -----------------------------
# Main: Find album URL via API, then scrape tracklist
# -----------------------------
def main():
    load_dotenv(PROJECT_ROOT / ".env")
    token = os.getenv("GENIUS_API_KEY")

    if not token:
        raise RuntimeError(
            "Missing GENIUS_API_KEY. Add it to a .env file in your project root."
        )

    # 1) Find a candidate song id via search
    song_id = pick_candidate_song_id(token, ALBUM_NAME, ARTIST_NAME)
    if not song_id:
        raise RuntimeError("Could not find any Genius search results to bootstrap album discovery.")

    # 2) Fetch song metadata and locate album URL
    song = genius_song(token, song_id)
    album = song.get("album")
    if not album or not album.get("url"):
        raise RuntimeError(
            "Found a song, but Genius did not return album info for it. "
            "Try changing ALBUM_NAME / ARTIST_NAME or pick a different song manually."
        )

    album_name_api = album.get("name", "")
    album_url = album["url"]

    # Soft check (album names might differ slightly)
    if normalize(ALBUM_NAME) not in normalize(album_name_api):
        print(f"Note: API album name '{album_name_api}' doesn't closely match '{ALBUM_NAME}'. Proceeding anyway.")
    print(f"Using album page: {album_url}")

    # 3) Scrape tracklist from album page
    track_pairs = scrape_album_tracklist(album_url, expected_album_name=ALBUM_NAME)

    # 4) Build tracks.csv
    rows = []
    for track_number, raw_title in track_pairs:
        track_name = clean_track_name(raw_title)
        rows.append(
            {
                "track_id": make_track_id(ALBUM_SLUG, track_number),
                "track_number": int(track_number),
                "track_name": track_name,
                "track_name_raw": raw_title,
            }
        )

    df = pd.DataFrame(rows).sort_values("track_number")

    # Basic validation
    if df["track_id"].duplicated().any():
        raise RuntimeError("Duplicate track_id detected (unexpected).")
    if (df["track_name"].astype(str).str.len() == 0).any():
        bad = df[df["track_name"].astype(str).str.len() == 0]
        raise RuntimeError(f"Some tracks became empty after cleaning:\n{bad}")

    df.to_csv(OUT_TRACKS, index=False)
    print(f"Wrote {len(df)} tracks to {OUT_TRACKS}")


if __name__ == "__main__":
    main()
