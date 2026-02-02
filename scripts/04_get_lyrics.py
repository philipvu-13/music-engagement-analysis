# scripts/04_get_lyrics.py
"""
04_get_lyrics.py

Goal:
- Use Genius API to FIND the correct song page (stable)
- Scrape the lyrics text from the Genius song page (because Genius API does not return full lyrics)
- Clean lyrics to remove Genius header junk (contributors, translations, title line)
- Compute simple lyric metrics
- Output: data/lyrics.csv

Requires:
  pip install pandas requests beautifulsoup4 python-dotenv

.env (in project root) should contain:
  GENIUS_API_KEY=YOUR_TOKEN
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


# -----------------------------
# Config
# -----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

IN_TRACKS = DATA_DIR / "tracks.csv"
OUT_LYRICS = DATA_DIR / "lyrics.csv"

GENIUS_API_BASE = "https://api.genius.com"

ARTIST_NAME = "A$AP Rocky"
SLEEP_BETWEEN_REQUESTS_SEC = 0.7


# -----------------------------
# Text helpers
# -----------------------------
def normalize_text(s: str) -> str:
    s = (s or "").lower().strip()
    s = s.replace("’", "'")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9\s']", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def clean_lyrics_text(text: str, track_name: str) -> str:
    """
    Robust lyric cleaner:
    - Removes EVERYTHING above "<Track Name> Lyrics"
    - Removes [Chorus], [Verse], etc.
    - Keeps spoken intros / skits
    """
    if not text:
        return ""

    t = text.replace("\r\n", "\n").replace("\r", "\n")

    # --- KEY FIX: remove Genius page junk ---
    # Keep only text AFTER "<Track Name> Lyrics"
    title_pattern = re.compile(
        rf"{re.escape(track_name)}\s+Lyrics",
        flags=re.IGNORECASE
    )
    match = title_pattern.search(t)
    if match:
        t = t[match.end():]

    # Remove bracketed section labels
    t = re.sub(r"\[.*?\]", "", t)

    # Normalize spacing
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)

    return t.strip()


def tokenize_words(text: str) -> List[str]:
    """
    Counts ALL words:
    - contractions
    - numbers
    - slang
    """
    t = normalize_text(text)
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", t)


def lyric_metrics(lyrics_text: str) -> Tuple[int, int, float]:
    words = tokenize_words(lyrics_text)
    wc = len(words)
    uwc = len(set(words))
    rr = 1.0 - (uwc / wc) if wc > 0 else 0.0
    return wc, uwc, float(rr)


# -----------------------------
# Genius API helpers
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
    return r.json().get("response", {}).get("hits", [])[:per_page]


def genius_song(token: str, song_id: int) -> dict:
    r = requests.get(
        f"{GENIUS_API_BASE}/songs/{song_id}",
        headers=genius_headers(token),
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("response", {}).get("song", {})


@dataclass
class GeniusMatch:
    song_id: int
    score: int


def pick_best_genius_hit(track_name: str, hits: List[dict], artist_name: str) -> Optional[int]:
    if not hits:
        return None

    track_n = normalize_text(track_name)
    artist_n = normalize_text(artist_name)

    best: Optional[GeniusMatch] = None

    for h in hits:
        r = h.get("result", {})
        song_id = r.get("id")
        if not song_id:
            continue

        title = normalize_text(r.get("title", ""))
        artist = normalize_text(r.get("primary_artist", {}).get("name", ""))

        score = 0
        if artist_n in artist:
            score += 50
        if track_n in title:
            score += 30

        if best is None or score > best.score:
            best = GeniusMatch(song_id=song_id, score=score)

    return best.song_id if best else None


# -----------------------------
# Scrape lyrics
# -----------------------------
def scrape_genius_lyrics(song_url: str) -> str:
    r = requests.get(song_url, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    blocks = soup.select('div[data-lyrics-container="true"]')
    if blocks:
        return "\n".join(b.get_text("\n", strip=True) for b in blocks)

    old = soup.select_one(".lyrics")
    if old:
        return old.get_text("\n", strip=True)

    return ""


# -----------------------------
# Main
# -----------------------------
def main():
    load_dotenv(PROJECT_ROOT / ".env")
    token = os.getenv("GENIUS_API_KEY")

    if not token:
        raise RuntimeError("Missing GENIUS_API_KEY in .env")

    tracks = pd.read_csv(IN_TRACKS)

    rows = []
    for _, t in tracks.sort_values("track_number").iterrows():
        track_id = str(t["track_id"])
        track_name = str(t["track_name"])

        print(f"[LYRICS] {track_id} | {track_name}")

        hits = genius_search(token, f"{ARTIST_NAME} {track_name}")
        song_id = pick_best_genius_hit(track_name, hits, ARTIST_NAME)

        if not song_id:
            rows.append({"track_id": track_id})
            continue

        song = genius_song(token, song_id)
        url = song.get("url", "")
        artist = (song.get("primary_artist") or {}).get("name", "")
        title = song.get("title", "")

        raw = scrape_genius_lyrics(url)
        clean = clean_lyrics_text(raw, track_name)

        wc, uwc, rr = lyric_metrics(clean)

        rows.append({
            "track_id": track_id,
            "lyrics_text": clean,
            "word_count": wc,
            "unique_word_count": uwc,
            "repeat_ratio": rr,
            "genius_song_id": song_id,
            "genius_url": url,
            "match_confidence": "high" if wc > 50 else "low",
            "genius_title": title,
            "genius_primary_artist": artist,
        })

        time.sleep(SLEEP_BETWEEN_REQUESTS_SEC)

    pd.DataFrame(rows).to_csv(OUT_LYRICS, index=False)
    print(f"\nWrote {len(rows)} rows to {OUT_LYRICS}")


if __name__ == "__main__":
    main()
