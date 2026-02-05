# scripts/04_get_lyrics.py
"""
04_get_lyrics.py - Genius lyrics scraper + basic lyric metrics

What it does:
- Reads data/tracks.csv
- Finds the next unprocessed track (one song per run)
- Uses Genius API to find the best song URL
- Scrapes lyrics from the Genius song page (lyrics containers only)
- Cleans lyrics:
  - removes description/metadata blurbs that sometimes appear at the top
  - removes multi-line section headers like [Chorus: ...]
  - removes other Genius junk (You might also like, Embed, language menu items, etc.)
- Computes metrics (word count, unique word count, repetition ratio)
- Appends to data/lyrics.csv

Requirements:
  pip install pandas requests beautifulsoup4 python-dotenv

.env (project root) should contain:
  GENIUS_API_KEY=YOUR_TOKEN
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

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

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 30
SLEEP_BETWEEN_REQUESTS_SEC = 0.25


# -----------------------------
# Helpers: cleaning & IDs
# -----------------------------
def normalize_whitespace(s: str) -> str:
    s = re.sub(r"\r\n?", "\n", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def clean_track_name(name: str) -> str:
    """
    Remove view counts / "Lyrics" / extra spacing from scraped track titles.
    """
    if name is None:
        return ""
    s = str(name).strip()
    s = re.sub(r"\s+", " ", s)

    # remove things like 108.2K, 3.1M etc
    s = re.sub(r"\b\d+(\.\d+)?[KMB]\b", "", s, flags=re.IGNORECASE)

    # remove trailing "Lyrics"
    s = re.sub(r"\bLyrics\b", "", s, flags=re.IGNORECASE)

    # tighten parentheses spacing
    s = re.sub(r"\s+\)", ")", s)
    s = re.sub(r"\(\s+", "(", s)

    s = re.sub(r"\s{2,}", " ", s)
    return s.strip(" -–—")


def clean_lyrics_text(raw: str, track_name: str) -> str:
    """
    Cleans Genius lyric text:
    - removes multi-line bracket headers [Chorus: ...]
    - removes description blurbs at the TOP (when they leak into lyrics containers)
    - removes footer junk and language menus
    """
    if not raw:
        return ""

    text = re.sub(r"\r\n?", "\n", raw)

    # Remove multi-line section headers like:
    # [Chorus: A$AP Rocky,
    #  Brent Faiyaz
    #  &
    #  Both]
    # NOTE: [^]] includes newlines too, so this catches multi-line headers.
    text = re.sub(
        r"\[(?:(?:pre|post)-?chorus|chorus|verse|bridge|intro|outro|refrain|hook|interlude|skit)[^]]*\]",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # normalize spacing inside parentheses (keep adlibs)
    text = re.sub(r"\(\s*([\s\S]*?)\s*\)", r"(\1)", text)

    # remove common footer junk
    text = re.sub(r"\n\s*You might also like\s*\n.*", "\n", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"\n\s*Embed\s*\n.*$", "\n", text, flags=re.IGNORECASE | re.DOTALL)

    # --- Remove Genius "About" description blurb if it got mixed into the top ---
    # Normalize track name once for all title/description matching
    def _norm_for_title_match_early(s: str) -> str:
        s = s.lower().strip()
        s = (s
             .replace("\u2019", "'")  # '
             .replace("\u2018", "'")  # '
             .replace("\u201c", '"')  # "
             .replace("\u201d", '"')  # "
             )
        s = (s
             .replace("\u2013", "-")  # –
             .replace("\u2014", "-")  # —
             )
        s = re.sub(r"\s+", " ", s)
        return s

    tn_lower = _norm_for_title_match_early(track_name)
    lines0 = [ln.strip() for ln in text.split("\n")]

    def looks_like_description_line(ln: str) -> bool:
        s = ln.strip()
        if not s:
            return False
        sl = s.lower()

        bad_phrases = [
            "is the",
            "track off",
            "studio album",
            "highly anticipated",
            "featuring",
            "the track is about",
            "this track is about",
            "the song is about",
            "produced by",
            "released",
            "release",
            "read more",
        ]

        # mentions title + typical about-language
        if tn_lower and tn_lower in sl and any(p in sl for p in bad_phrases):
            return True

        # generic about-language near top (often long sentences)
        if any(p in sl for p in bad_phrases) and len(s) > 40:
            return True

        # teaser ellipsis lines
        if s.endswith("…") or s.endswith("..."):
            return True

        return False

    # Drop description-like lines that appear within the first few non-empty
    # lines (some Genius pages insert short metadata lines or blank lines
    # before the actual blurb). Remove matches among the first N non-empty
    # lines rather than requiring it to be the very first line.
    max_top_nonempty = 8
    nonempty_seen = 0
    i = 0
    while i < len(lines0) and nonempty_seen < max_top_nonempty:
        if not lines0[i].strip():
            i += 1
            continue

        if looks_like_description_line(lines0[i]):
            lines0.pop(i)
            # do not increment i so next item shifts into this index
            continue

        nonempty_seen += 1
        i += 1

    text = "\n".join(lines0)

    # Line-level cleanup
    lines = [ln.strip() for ln in text.split("\n")]

    language_menu = {
        "Deutsch",
        "Türkçe",
        "Русский",
        "Русский (Russian)",
        "Português",
        "Español",
        "Français",
        "Italiano",
        "Nederlands",
        "Polski",
        "Svenska",
        "한국어",
        "日本語",
        "中文",
        "العربية",
        "हिन्दी",
        "Bahasa Indonesia",
    }

    # Helper to normalize punctuation for title matching (handles curly quotes, smart dashes, etc.)
    def _norm_for_title_match(s: str) -> str:
        s = s.lower().strip()
        # Normalize smart apostrophes/quotes to ASCII using Unicode escapes
        s = (s
             .replace("\u2019", "'")  # '
             .replace("\u2018", "'")  # '
             .replace("\u201c", '"')  # "
             .replace("\u201d", '"')  # "
             )
        # Normalize common dash variants
        s = (s
             .replace("\u2013", "-")  # –
             .replace("\u2014", "-")  # —
             )
        # Normalize whitespace
        s = re.sub(r"\s+", " ", s)
        return s

    cleaned_lines: List[str] = []
    for ln in lines:
        if not ln:
            continue

        if ln in language_menu:
            continue

        # redundant now, but harmless
        if ln.startswith("[") and ln.endswith("]"):
            continue

        # remove title lines like "DON'T BE DUMB / TRIP BABY Lyrics" (handles curly quotes, dashes, etc.)
        if tn_lower:
            ln_norm = _norm_for_title_match(ln)
            tn_norm = _norm_for_title_match(track_name)

            if ln_norm == f"{tn_norm} lyrics":
                continue
            if ln_norm.endswith(" lyrics") and tn_norm in ln_norm:
                continue

        # remove contributors/translations lines if they show up
        if re.fullmatch(r"\d+\s+contributors?", ln, flags=re.IGNORECASE):
            continue
        if re.fullmatch(r"translations?", ln, flags=re.IGNORECASE):
            continue

        cleaned_lines.append(ln)

    # --- Remove description-like lines anywhere in the text ---
    def looks_like_description_anywhere(ln: str) -> bool:
        s = ln.strip()
        if not s:
            return False
        sl = s.lower()


        # Strong metadata signals (safe to remove when present in reasonably long lines)
        strong_phrases = [
            "released",
            "music video",
            "released on",
            "released in",
            "premiered",
            "announced",
            "release was announced",
        ]

        # Weaker phrases that are common words and may appear in lyrics; only
        # treat them as metadata when they appear with the track name or other
        # strong context.
        weak_phrases = [
            "album",
            "in conjunction",
            "in anticipation",
            "produced by",
            "followed",
            "featuring",
            "feat.",
        ]

        # If a long line contains any strong metadata phrase, drop it.
        if any(p in sl for p in strong_phrases) and len(s) > 30:
            return True

        # If a weak phrase appears together with the track title, it's likely
        # part of a description and can be removed when long.
        if tn_lower and any(p in sl for p in weak_phrases) and tn_lower in sl and len(s) > 30:
            return True

        # The word "single" is common in lyrics (e.g. "every single little...")
        # Only treat it as metadata when it clearly means a release "single".
        if "single" in sl:
            # Clear music-release phrases like "lead single", "debut single", etc.
            if re.search(r"\b(?:lead|debut|second|third|promotional)\s+single\b", sl) and len(s) > 30:
                return True

            # "the single" / "a single" can be metadata, but require extra context words
            if re.search(r"\b(?:the|a|this|that|his|her|their|its)\s+single\b", sl):
                if len(s) > 30 and any(p in sl for p in (strong_phrases + ["album", "track", "song"])):
                    return True


        # Month name + reasonably long -> likely a release sentence
        if re.search(
            r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
            sl,
            flags=re.IGNORECASE,
        ) and len(s) > 20:
            return True

        # Year-like patterns can be real lyrics (e.g., "That was 2015")
        # Only remove if it ALSO looks like metadata (released/premiered/etc.)
        if re.search(r"\b(19|20)\d{2}\b", s):
            if any(p in sl for p in strong_phrases) and len(s) > 30:
                return True
            # Otherwise, keep it as lyrics
            return False


        return False

    filtered_lines = [ln for ln in cleaned_lines if not looks_like_description_anywhere(ln)]

    out = "\n".join(filtered_lines)
    out = normalize_whitespace(out)
    return "\n" + out.strip()


# -----------------------------
# Lyric metrics
# -----------------------------
WORD_RE = re.compile(r"[A-Za-z0-9']+")


def _tokenize_words(text: str) -> List[str]:
    if not text:
        return []
    return [w.lower() for w in WORD_RE.findall(text)]


def count_words(text: str) -> int:
    return len(_tokenize_words(text))


def count_unique_words(text: str) -> int:
    return len(set(_tokenize_words(text)))


def repetition_ratio(text: str) -> float:
    """
    Simple repetition score:
      1 - (unique_words / total_words)
    """
    words = _tokenize_words(text)
    total = len(words)
    if total == 0:
        return 0.0
    unique = len(set(words))
    return round(1.0 - (unique / total), 6)


# -----------------------------
# Genius API wrappers
# -----------------------------
@dataclass
class GeniusClient:
    access_token: str

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}", **DEFAULT_HEADERS}

    def search_song(self, query: str) -> Optional[Dict]:
        url = f"{GENIUS_API_BASE}/search"
        r = requests.get(url, headers=self._headers(), params={"q": query}, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        hits = data.get("response", {}).get("hits", [])
        return hits[0].get("result") if hits else None


def best_song_url_for_track(
    gc: GeniusClient,
    track_name: str,
    artist_name: str,
    album_name: Optional[str] = None,
) -> Optional[str]:
    query = f"{artist_name} {track_name}"
    if album_name:
        query = f"{query} {album_name}"
    result = gc.search_song(query)
    return result.get("url") if result else None


# -----------------------------
# Scraping
# -----------------------------
def _join_lyrics_blocks(blocks: List) -> str:
    parts: List[str] = []
    for b in blocks:
        t = b.get_text("\n", strip=True)
        if not t:
            continue

        # Drop ONLY the "Read More" line(s), not everything after it
        lines: List[str] = []
        for ln in t.split("\n"):
            if re.fullmatch(r"read more", ln.strip(), flags=re.IGNORECASE):
                continue
            lines.append(ln)

        t2 = "\n".join(lines).strip()
        if t2:
            parts.append(t2)

    return "\n\n".join(parts).strip()


def scrape_genius_lyrics(song_url: str) -> str:
    """
    Scraper that targets the lyric root / containers (avoids page descriptions when possible).
    Now with a robust fallback that gathers ALL lyric containers on the page.
    """
    r = requests.get(song_url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    chunks: List[str] = []

    # 1) Prefer lyric root if present
    lyrics_root = soup.find("div", {"id": "lyrics-root-id"}) or soup.find("div", class_=re.compile(r"Lyrics__Root"))
    if lyrics_root:
        blocks = lyrics_root.find_all("div", {"data-lyrics-container": "true"})
        if blocks:
            chunks.append(_join_lyrics_blocks(blocks))

    # 2) aria-label "Lyrics" section
    blocks2 = soup.select('section[aria-label="Lyrics"] div[data-lyrics-container="true"]')
    if blocks2:
        chunks.append(_join_lyrics_blocks(blocks2))

    # 3) GLOBAL fallback: any lyrics containers anywhere on the page
    blocks3 = soup.select('div[data-lyrics-container="true"]')
    if blocks3:
        chunks.append(_join_lyrics_blocks(blocks3))

    # 4) legacy fallback
    legacy = soup.select_one("div.lyrics")
    if legacy:
        chunks.append(legacy.get_text("\n", strip=True))

    # combine + de-dupe while preserving order
    combined = "\n\n".join([c for c in chunks if c and c.strip()]).strip()
    if not combined:
        return ""

    # light de-dupe: remove exact duplicate blocks
    seen = set()
    out_blocks = []
    for block in combined.split("\n\n"):
        b = block.strip()
        if not b:
            continue
        if b in seen:
            continue
        seen.add(b)
        out_blocks.append(b)

    return "\n\n".join(out_blocks).strip()



# -----------------------------
# Main Execution
# -----------------------------
def _already_done() -> set:
    """
    Track IDs that already exist in lyrics.csv (so we only do one new track per run).
    """
    if not OUT_LYRICS.exists():
        return set()
    try:
        done = pd.read_csv(OUT_LYRICS, usecols=["track_id"], dtype=str)
        return set(done["track_id"].fillna("").str.strip())
    except Exception:
        # If the file exists but is malformed, treat as none done
        return set()


def main() -> None:
    load_dotenv()
    token = os.getenv("GENIUS_API_KEY", "").strip()
    if not token:
        raise SystemExit("Missing GENIUS_API_KEY in your .env file.")

    if not IN_TRACKS.exists():
        raise SystemExit(f"Missing input file: {IN_TRACKS}")

    tracks = pd.read_csv(IN_TRACKS)
    done_ids = _already_done()
    # Process all unprocessed tracks in one run, appending each result immediately
    targets = []
    for i, row in tracks.iterrows():
        tid = str(row.get("track_id", "")).strip()
        if tid and tid not in done_ids:
            targets.append((i, row))

    if not targets:
        print("All tracks are already processed.")
        return

    print(f"\nProcessing {len(targets)} unprocessed track(s)...\n")
    print("=" * 60)

    gc = GeniusClient(access_token=token)
    write_header = not OUT_LYRICS.exists()

    for idx, (i, row) in enumerate(targets, 1):
        track_id = str(row.get("track_id", "")).strip()
        track_name = clean_track_name(str(row.get("track_name", "")).strip())
        artist_name = str(row.get("artist_name", "A$AP Rocky")).strip()
        album_name = row.get("album_name", None)
        album_name = str(album_name).strip() if isinstance(album_name, str) and album_name.strip() else None

        print(f"[{idx}/{len(targets)}] Fetching: {track_name}")
        print("-" * 60)

        url = best_song_url_for_track(gc, track_name, artist_name, album_name)

        lyrics = ""
        if not url:
            print("No Genius URL found.")
        else:
            print(f"URL: {url}")
            try:
                time.sleep(SLEEP_BETWEEN_REQUESTS_SEC)
                raw_lyrics = scrape_genius_lyrics(url)
                lyrics = clean_lyrics_text(raw_lyrics, track_name)
                print(f"Scraped {count_words(lyrics)} words.")
            except Exception as e:
                print(f"Error scraping: {e}")
                lyrics = ""

        print("-" * 60)
        print(lyrics if lyrics.strip() else "(No lyrics found)")
        print("-" * 60 + "\n")

        new_row = pd.DataFrame([
            {
                "track_id": track_id,
                "track_name": track_name,
                "genius_url": url or "",
                "lyrics": lyrics,
                "word_count": count_words(lyrics),
                "unique_word_count": count_unique_words(lyrics),
                "repetition_ratio": repetition_ratio(lyrics),
            }
        ])

        # Append row immediately to preserve progress if interrupted
        try:
            new_row.to_csv(
                OUT_LYRICS,
                mode="a",
                header=write_header,
                index=False,
                encoding="utf-8",
            )
            write_header = False
            print(f"Saved to {OUT_LYRICS}\n")
        except Exception as e:
            print(f"Failed to write row for {track_id}: {e}")
            # continue to next track


if __name__ == "__main__":
    main()
