# Music Engagement Analysis: *Don’t Be Dumb* — A$AP Rocky  
A production-style analytics pipeline that quantifies how lyrical structure influences early-release YouTube engagement.

Built using Python, PostgreSQL, Docker, and Metabase, this project transforms public API data into reproducible, decision-ready insights.

---

## 📊 Sample Visualization
This scatter plot visualizes the relationship between lyrical repetition and normalized engagement quality during the early release window.
![Dashboard Screenshot](assets/metabase/01_Metabase-Repeat%20Ratio%20vs%20Window%20Engagement%20Score.png)

---

## 💡 What This Project Demonstrates
- Designing a multi-source ETL pipeline using public APIs
- Building a normalized analytics schema in PostgreSQL
- Creating production-style SQL views for dashboard consumption
- Translating data insights into strategic recommendations

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
### Architecture Overview
```
YouTube Data API      Genius API
        │                   │
        └───────┬───────────┘
                ▼
        Python ETL Pipeline
                ▼
        PostgreSQL Database
                ▼
        SQL View (track_analysis_v)
                ▼
        Metabase Dashboard
```
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

## 🚀 Quickstart (Run Locally)

This project can be fully reproduced locally using Docker, PostgreSQL, and Python.

---

### 📋 Prerequisites

- Docker + Docker Compose
- Python 3.10+
- YouTube Data API key
- (Optional) Genius API token for lyrics

---

## 1️⃣ Clone the Repository

```bash
git clone https://github.com/philipvu-13/music-engagement-analysis.git
cd music-engagement-analysis
```

---

## 2️⃣ Create Environment Variables

Copy the example file:

```bash
cp .env.example .env
```

Open `.env` and add your API keys:

```env
YOUTUBE_API_KEY=your_youtube_api_key_here
GENIUS_ACCESS_TOKEN=your_genius_token_here
PGHOST=localhost
PGPORT=5432
PGDATABASE=dont_be_dumb
PGUSER=postgres
PGPASSWORD=postgres
```

---

## 3️⃣ Start Postgres + Metabase (Docker)

```bash
docker compose up -d
```

This will start:
- PostgreSQL (port 5432)
- Metabase (port 3000)

---

## 4️⃣ Create Database Tables

```bash
psql -h localhost -U postgres -d dont_be_dumb -f sql/01_schema.sql
```

You can also execute `sql/01_schema.sql` inside DBeaver if preferred.

---

## 5️⃣ Set Up Python Environment

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

Windows:
```bash
.venv\Scripts\activate
```

Mac/Linux:
```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 6️⃣ Run the ETL Pipeline

Run scripts in this order:

```bash
python scripts/01_pull_tracks.py
python scripts/02_match_youtube_videos.py
python scripts/03_pull_youtube_stats.py
python scripts/04_pull_lyrics.py
python scripts/05_load_to_postgres.py
```

---

## 7️⃣ Create the Analytics View

```bash
psql -h localhost -U postgres -d dont_be_dumb -f sql/02_views.sql
```

This creates the main analysis dataset:

`track_analysis_v`

---

## 8️⃣ Open Metabase

Open in your browser:

```
http://localhost:3000
```

When connecting to PostgreSQL use:

- Host: `postgres` (inside Docker network) OR `localhost`
- Port: `5432`
- Database: `dont_be_dumb`
- Username: `postgres`
- Password: `postgres`

Primary dataset for dashboards:

`track_analysis_v`

---

## 📦 Outputs

- Raw extracted data (CSV): `data/` (ignored by git)
- Database tables:
  - `tracks`
  - `youtube_videos`
  - `youtube_stats_snapshots`
  - `lyrics`
- Analytics view:
  - `track_analysis_v`
- Dashboard screenshots:
  - `assets/metabase/`

---

## 🧯 Troubleshooting

Port 5432 already in use?
Stop local Postgres or change Docker port mapping.

Metabase cannot connect?
- Inside Docker → Host = `postgres`
- From host machine → Host = `localhost`

psql not found?
Install PostgreSQL client tools or use DBeaver to execute SQL files.

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

## 🧩 Why This Matters

For artists, labels, and digital marketing teams, understanding early-release momentum vs engagement quality is critical for:

• Allocating promotional budget  
• Selecting singles  
• Prioritizing social content  
• Forecasting long-tail performance  

This framework can be generalized to any album release or media launch.

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

data/ (gitignore)
    # Raw CSV outputs generated via API pulls (not included due to API usage policies)
```

---

## 📌 Project Status  
✅ **MVP complete** – pipeline, database, dashboard, and analysis finalized.  
📘 **Refining documentation** and packaging for portfolio presentation.
