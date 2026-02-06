# Music Engagement Analysis — *Don’t Be Dumb* (A$AP Rocky)

Analyzing listener engagement and lyrical patterns from A$AP Rocky’s long awaited and newly released album, *Don’t Be Dumb*, using public APIs, SQL, and Python.

---

## 🧠 The Question
**How do lyrical patterns (repetition + length) relate to YouTube engagement and growth across tracks on *Don’t Be Dumb*?**

---

## 📌 What This Project Does
- Pulls track + video metadata and engagement stats from the **YouTube Data API**
- Pulls lyrics from **Genius**
- Loads everything into **PostgreSQL**
- Builds an analytics view (**`track_analysis_v`**) that outputs one clean, Metabase-friendly row per track
- Visualizes results in **Metabase** to compare lyrical patterns vs engagement

---

## 📊 Data Sources & Scope
**Sources**
- YouTube Data API (views, likes, comments)
- Genius (lyrics)

**Scope**
- Track-level analysis (**one primary YouTube video per track**)
- Snapshot window metrics based on repeated stat captures (e.g., **Jan 23, 2026 → Feb 4, 2026**)

---

## 🧰 Tech Stack
- Python (ETL scripts)
- PostgreSQL (storage + analytics layer)
- SQL (views + chart queries)
- Docker (local reproducible environment)
- Metabase (dashboard)

---

## 🗂 Repo Structure
```text
sql/
  01_schema.sql
  02_views.sql
  charts/
    01_scatter_repeat_ratio_vs_window_engagement_score.sql
    02_scatter_word_count_vs_window_engagement_score.sql
    03_bar_avg_window_engagement_by_repeat_bucket.sql
    04_bar_avg_window_engagement_by_word_count_bucket.sql
    05_table_top_tracks_window_engagement.sql
    06_line_view_velocity_over_time_top_5.sql
scripts/
  (your ETL scripts here)
assets/
  metabase/
    (chart screenshots + table export CSV)
data/
  (optional: raw/ or derived/ depending on what you commit)

## 🔧 How It Works (Pipeline)

Python scripts pull:

track list

YouTube video match per track

repeated YouTube stats snapshots over time

Genius lyrics + lyric stats

Load into Postgres tables:

tracks

youtube_videos

youtube_stats_snapshots

lyrics

Create the analytics view:

track_analysis_v (defined in sql/02_views.sql)

Metabase uses track_analysis_v for charts + uses the snapshot table for the time series chart

✅ Analytics Layer: track_analysis_v

The view is designed to be defensible and interview-ready:

One row per track (Metabase-friendly)

Deterministic “primary video” per track (official + best match + highest views)

Uses the latest snapshot for “as-of” metrics

Uses window deltas (start vs end) to measure growth during the capture window

Includes lyric metrics + buckets to segment tracks (repeat_bucket, word_count_bucket)

Key metrics:

window_engagement_score = weighted interactions per 1,000 new views during the window
(likes + 2×comments, normalized by new views)

views_delta_per_day = growth velocity during the window

lyric metrics: repeat_ratio, word_count, lexical_diversity

📈 Dashboard (Metabase)

Dashboard name: Don’t Be Dumb — Lyrics vs Engagement (YouTube)

Charts:

Repeat Ratio vs Window Engagement Score

Word Count vs Window Engagement Score

Avg Window Engagement Score by Repeat Bucket

Avg Window Engagement Score by Word Count Bucket

Top Tracks — Window Engagement (table)

View Velocity Over Time (Top 5 Tracks)

Screenshots and exports are saved under assets/metabase/.

🔍 Findings (Supported by Charts)
1) Repetition alone does not strongly predict engagement quality

Correlation between repeat_ratio and window_engagement_score is very weak (~0.07).

Most of the highest engagement tracks cluster around moderate repetition.

2) Word count has a clearer relationship with engagement quality

Correlation between word_count and window_engagement_score is moderately positive (~0.49).

Longer lyrical tracks tended to generate more interaction per new view in the window.

Note: word_count_bucket sizes are uneven (most tracks are 401+), so bucket results are directional.

3) Medium repetition tracks averaged the highest window engagement score

Average window_engagement_score by repeat_bucket:

Med: ≈ 17.64 (n=14)

High: ≈ 13.45 (n=4)

Low: ≈ 6.16 (n=1)

4) The “most engaging” tracks differ from the “fastest growing” tracks

Top by window_engagement_score:

ROBBERY (26.74), FLACKITO JODYE (26.48), FISH N STEAK (24.74), WHISKEY (21.71), STAY HERE 4 LIFE (20.36)

Top by views_delta_per_day:

HELICOPTER (333,990/day), PUNK ROCKY (219,935/day), I Smoked Away My Brain (136,897/day), STAY HERE 4 LIFE (55,483/day), STOLE YA FLOW (39,391/day)

5) Momentum decays over the window for viral tracks

In the “velocity over time” chart, top growth tracks show early spikes followed by tapering — consistent with typical release dynamics.

🎯 Recommendations (Actionable)

Use a Momentum vs Engagement framework to decide what to push

High momentum / lower engagement quality → optimize for reach (more formats, more distribution)

High engagement quality / lower momentum → optimize for conversation (lyric breakdowns, prompts, reactions)

High on both → prioritize as flagship support
Example: STAY HERE 4 LIFE performs well on both.

Use comment-heavy tracks for interactive content
Tracks with high comment intensity are better for:

“What did this bar mean?” posts

reaction videos

discussion prompts

For a newly released album, lead with window metrics
Use views_delta_per_day + window_engagement_score to describe early performance instead of total views alone.

⚠️ Limitations

Public APIs don’t include watch time, retention, or traffic sources.

“Primary video per track” selection can affect totals if multiple major uploads exist.

Results reflect the snapshot window (e.g., Jan 23 → Feb 4, 2026); rankings can change as counts evolve.

Some buckets have small sample sizes (e.g., low/medium word-count buckets).

🚧 Status

MVP complete — refining write-up and packaging for portfolio.