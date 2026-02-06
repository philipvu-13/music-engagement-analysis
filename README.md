# Music Engagement Analysis: *Don’t Be Dumb* — A$AP Rocky  
*Analyzing lyrical patterns and listener engagement across the newly released album using YouTube and Genius data*

---

## 🎯 Objective  
To investigate the relationship between **lyrical patterns** (repetition, length) and **YouTube engagement trends** across tracks from A$AP Rocky's album *Don't Be Dumb*, using a data pipeline built with public APIs, SQL, and Python.

---

## 📊 Key Question  
**How do lyrical repetition and word count relate to audience engagement and growth momentum in the weeks following release?**

---

## 🛠️ Tech Stack  
- **Python** – ETL, API integration, data processing  
- **PostgreSQL** – Centralized data storage & analytics layer  
- **SQL Views** – Clean, reusable analytics tables  
- **Docker** – Reproducible local environment  
- **Metabase** – Interactive dashboard & visualization  
- **APIs** – YouTube Data API, Genius API

---

## 🔁 Data Pipeline  

1. **Extract**  
   - Track list and metadata  
   - YouTube video matches (primary video per track)  
   - Daily engagement snapshots (views, likes, comments) via YouTube Data API  
   - Lyrics and lyric-level metrics via Genius API  

2. **Load**  
   Raw data is loaded into PostgreSQL tables:  
   - `tracks`  
   - `youtube_videos`  
   - `youtube_stats_snapshots`  
   - `lyrics`

3. **Transform**  
   - Primary video selection per track (official + highest views)  
   - Calculation of window-based growth and engagement scores  
   - Lyric analysis: repeat ratio, word count, lexical diversity  
   - Bucketing for categorical analysis (`repeat_bucket`, `word_count_bucket`)

4. **Analyze**  
   Analytics view `track_analysis_v` provides one row per track with key metrics:  
   - `window_engagement_score` – weighted interactions per 1k new views  
   - `views_delta_per_day` – growth velocity during snapshot window  
   - Lyric stats and derived segments

---

## 📈 Dashboard (Metabase)  
**Title:** *Don't Be Dumb — Lyrics vs Engagement (YouTube)*  

**Charts include:**  
- Repeat Ratio vs Window Engagement Score  
- Word Count vs Window Engagement Score  
- Avg Engagement by Repeat Bucket  
- Avg Engagement by Word Count Bucket  
- Top Tracks — Window Engagement Score (table)  
- View Velocity Over Time (Top 5 Tracks)  

📁 Dashboard exports and screenshots are stored in `assets/metabase/`.

---

## 📌 Key Findings  

### 1. **Repetition alone does not strongly predict engagement quality**  
Correlation between `repeat_ratio` and `window_engagement_score` is weak (~0.07).  
Highest-engagement tracks cluster in the moderate repetition range.

### 2. **Word count has a clearer positive relationship with engagement**  
Correlation between `word_count` and engagement score is moderately positive (~0.49).  
Longer lyrical tracks tended to drive more interactions per new view.

### 3. **Medium-repetition tracks averaged the highest engagement score**  
- **Medium repetition:** ≈ 17.64 (14 tracks)  
- **High repetition:** ≈ 13.45 (4 tracks)  
- **Low repetition:** ≈ 6.16 (1 track)

### 4. **"Most engaging" differs from "fastest growing" tracks**  
| Rank | By Engagement Score               | By Growth Velocity (views/day)      |
|------|-----------------------------------|-------------------------------------|
| 1    | ROBBERY (26.74)                   | HELICOPTER (333,990)                |
| 2    | FLACKITO JODYE (26.48)            | PUNK ROCKY (219,935)                |
| 3    | FISH N STEAK (24.74)              | I Smoked Away My Brain (136,897)    |

### 5. **Viral tracks show early spikes followed by decay**  
Consistent with typical album release dynamics—momentum tapers after initial surge.

---

## 🚀 Actionable Recommendations  

### 1. **Adopt a *Momentum vs Engagement* framework**  
- **High momentum, lower engagement** → Optimize for reach (short clips, broad distribution)  
- **High engagement, lower momentum** → Foster conversation (lyric breakdowns, reactions)  
- **High both** → Prioritize as flagship content (e.g., *STAY HERE 4 LIFE*)

### 2. **Leverage comment-heavy tracks for interactive content**  
Tracks with high comment ratios are ideal for:  
- "What did this bar mean?" social prompts  
- Fan reaction videos  
- Lyric discussion threads

### 3. **Use window-based metrics for early release analysis**  
For newly released albums, track performance using:  
- `views_delta_per_day` (growth velocity)  
- `window_engagement_score` (quality of interactions)  
…rather than cumulative totals alone.

---

## ⚠️ Limitations & Notes  
- **Data sources:** Public APIs exclude watch time, retention, and traffic sources.  
- **Video selection:** "Primary video per track" is deterministic but may exclude alternate uploads.  
- **Time window:** Findings reflect snapshot period (Jan 23 – Feb 4, 2026); rankings may shift over time.  
- **Sample size:** Some lyric buckets contain few tracks—interpret trends directionally.

---

## 📁 Repository Structure  
```
sql/
├── 01_schema.sql
├── 02_views.sql
└── charts/
    ├── 01_scatter_repeat_ratio_vs_window_engagement_score.sql
    ├── 02_scatter_word_count_vs_window_engagement_score.sql
    ├── 03_bar_avg_window_engagement_by_repeat_bucket.sql
    ├── 04_bar_avg_window_engagement_by_word_count_bucket.sql
    ├── 05_table_top_tracks_window_engagement.sql
    └── 06_line_view_velocity_over_time_top_5.sql

scripts/
    # ETL and data processing scripts

assets/metabase/
    # Dashboard screenshots and exported CSVs

data/
    # Optional raw/processed data samples
```

---

## 📌 Project Status  
✅ **MVP complete** – pipeline, database, dashboard, and analysis finalized.  
📘 **Refining documentation** and packaging for portfolio presentation.