-- sql/02_views.sql
-- track_analysis_v: one row per track (Metabase-friendly)
-- Includes:
--   (1) latest "as-of" stats
--   (2) window growth stats using earliest + latest snapshots available per video

CREATE OR REPLACE VIEW track_analysis_v AS
WITH stats_window AS (
    -- For each video: get earliest + latest snapshot in your captured dataset
    SELECT
        s.youtube_video_id,

        -- window bounds
        MIN(s.captured_at) AS window_start_at,
        MAX(s.captured_at) AS window_end_at
    FROM youtube_stats_snapshots s
    GROUP BY s.youtube_video_id
),
stats_start AS (
    -- earliest snapshot row per video
    SELECT DISTINCT ON (s.youtube_video_id)
        s.youtube_video_id,
        s.captured_at AS start_captured_at,
        s.view_count  AS views_start,
        s.like_count  AS likes_start,
        s.comment_count AS comments_start
    FROM youtube_stats_snapshots s
    ORDER BY s.youtube_video_id, s.captured_at ASC
),
stats_end AS (
    -- latest snapshot row per video
    SELECT DISTINCT ON (s.youtube_video_id)
        s.youtube_video_id,
        s.captured_at AS end_captured_at,
        s.view_count  AS views_end,
        s.like_count  AS likes_end,
        s.comment_count AS comments_end
    FROM youtube_stats_snapshots s
    ORDER BY s.youtube_video_id, s.captured_at DESC
),
video_scored AS (
    -- Join videos to window stats and rank a deterministic "primary video" per track
    SELECT
        v.track_id,
        v.youtube_video_id,
        v.youtube_title,
        v.channel_title,
        v.published_at::timestamptz AS published_at,
        v.is_official,
        v.match_confidence,

        sw.window_start_at,
        sw.window_end_at,

        ss.start_captured_at,
        ss.views_start,
        ss.likes_start,
        ss.comments_start,

        se.end_captured_at,
        se.views_end,
        se.likes_end,
        se.comments_end,

        ROW_NUMBER() OVER (
            PARTITION BY v.track_id
            ORDER BY
                CASE WHEN v.is_official IS TRUE THEN 1 ELSE 0 END DESC,
                CASE
                    WHEN lower(v.match_confidence) = 'high' THEN 3
                    WHEN lower(v.match_confidence) = 'medium' THEN 2
                    WHEN lower(v.match_confidence) = 'low' THEN 1
                    ELSE 0
                END DESC,
                COALESCE(se.views_end, 0) DESC,
                v.published_at ASC
        ) AS video_rank
    FROM youtube_videos v
    LEFT JOIN stats_window sw
        ON sw.youtube_video_id = v.youtube_video_id
    LEFT JOIN stats_start ss
        ON ss.youtube_video_id = v.youtube_video_id
    LEFT JOIN stats_end se
        ON se.youtube_video_id = v.youtube_video_id
),
primary_video AS (
    SELECT *
    FROM video_scored
    WHERE video_rank = 1
),
lyrics_enriched AS (
    SELECT
        l.track_id,
        l.word_count,
        l.unique_word_count,
        COALESCE(
            l.repetition_ratio,
            CASE
                WHEN l.word_count IS NOT NULL AND l.word_count <> 0
                    THEN 1.0 - (l.unique_word_count::numeric / l.word_count::numeric)
                ELSE NULL
            END
        ) AS repeat_ratio
    FROM lyrics l
)
SELECT
    -- Track identity
    t.track_id,
    t.track_number,
    t.track_name,

    -- Primary YouTube video metadata
    pv.youtube_video_id AS primary_video_id,
    pv.youtube_title AS primary_youtube_title,
    pv.channel_title AS primary_channel_title,
    pv.published_at AS primary_published_at,

    -- Capture window bounds (for your dataset)
    pv.window_start_at,
    pv.window_end_at,

    -- Latest "as-of" stats (end of window)
    pv.end_captured_at AS stats_captured_at,
    pv.views_end       AS views,
    pv.likes_end       AS likes,
    pv.comments_end    AS comments,

    -- Lifetime normalization (as of latest snapshot time)
    GREATEST(
        1,
        FLOOR(
            EXTRACT(EPOCH FROM (COALESCE(pv.end_captured_at, NOW()) - pv.published_at)) / 86400
        )::int
    ) AS days_since_publish,

    (pv.views_end::numeric
        / NULLIF(
            GREATEST(
                1,
                FLOOR(EXTRACT(EPOCH FROM (COALESCE(pv.end_captured_at, NOW()) - pv.published_at)) / 86400)::int
            ),
            0
        )
    ) AS views_per_day,

    ((pv.likes_end + pv.comments_end)::numeric / NULLIF(pv.views_end, 0)) AS engagement_rate,
    (pv.comments_end::numeric / NULLIF(pv.likes_end, 0)) AS comment_to_like_ratio,
    (pv.likes_end::numeric * 1000 / NULLIF(pv.views_end, 0)) AS likes_per_1k_views,
    (pv.comments_end::numeric * 1000 / NULLIF(pv.views_end, 0)) AS comments_per_1k_views,

    ((pv.likes_end + (2 * pv.comments_end))::numeric * 1000 / NULLIF(pv.views_end, 0)) AS engagement_score,

    -- Window duration (your capture period, per video)
    GREATEST(
        1,
        FLOOR(EXTRACT(EPOCH FROM (pv.window_end_at - pv.window_start_at)) / 86400)::int
    ) AS window_days,

    -- Window growth (what changed during the measured period)
    pv.views_start,
    pv.likes_start,
    pv.comments_start,

    pv.views_end,
    pv.likes_end,
    pv.comments_end,

    (pv.views_end    - pv.views_start)    AS views_delta,
    (pv.likes_end    - pv.likes_start)    AS likes_delta,
    (pv.comments_end - pv.comments_start) AS comments_delta,

    -- Window velocity (fair “what was hot during our measurement” comparison)
    ((pv.views_end - pv.views_start)::numeric
        / NULLIF(
            GREATEST(
                1,
                FLOOR(EXTRACT(EPOCH FROM (pv.window_end_at - pv.window_start_at)) / 86400)::int
            ),
            0
        )
    ) AS views_delta_per_day,

    ((pv.likes_end - pv.likes_start)::numeric
        / NULLIF(
            GREATEST(
                1,
                FLOOR(EXTRACT(EPOCH FROM (pv.window_end_at - pv.window_start_at)) / 86400)::int
            ),
            0
        )
    ) AS likes_delta_per_day,

    ((pv.comments_end - pv.comments_start)::numeric
        / NULLIF(
            GREATEST(
                1,
                FLOOR(EXTRACT(EPOCH FROM (pv.window_end_at - pv.window_start_at)) / 86400)::int
            ),
            0
        )
    ) AS comments_delta_per_day,

    -- Window engagement: engagement on the NEW views during the window
    (((pv.likes_end - pv.likes_start) + (pv.comments_end - pv.comments_start))::numeric
        / NULLIF((pv.views_end - pv.views_start), 0)
    ) AS window_engagement_rate,

    (((pv.likes_end - pv.likes_start) + (2 * (pv.comments_end - pv.comments_start)))::numeric * 1000
        / NULLIF((pv.views_end - pv.views_start), 0)
    ) AS window_engagement_score,

    -- Lyrics metrics
    le.word_count,
    le.unique_word_count,
    le.repeat_ratio,

    CASE
        WHEN le.repeat_ratio IS NULL THEN NULL
        WHEN le.repeat_ratio < 0.55 THEN 'Low'
        WHEN le.repeat_ratio < 0.70 THEN 'Med'
        ELSE 'High'
    END AS repeat_bucket,

    CASE
        WHEN le.word_count IS NULL THEN NULL
        WHEN le.word_count <= 200 THEN '0–200'
        WHEN le.word_count <= 400 THEN '201–400'
        ELSE '401+'
    END AS word_count_bucket,

    (le.unique_word_count::numeric / NULLIF(le.word_count, 0)) AS lexical_diversity,

    -- Cross-domain bridge metrics (ties lyrical patterns to engagement)
    (
      ((pv.likes_end + (2 * pv.comments_end))::numeric * 1000 / NULLIF(pv.views_end, 0))
      / NULLIF((le.word_count::numeric / 100.0), 0)
    ) AS engagement_per_100_words,

    (pv.views_end::numeric / NULLIF(le.word_count, 0)) AS views_per_word,

    -- Optional: window velocity normalized by lyrics length (fun + interview-friendly)
    ((pv.views_end - pv.views_start)::numeric / NULLIF(le.word_count, 0)) AS views_delta_per_word

FROM tracks t
LEFT JOIN primary_video pv
    ON pv.track_id = t.track_id
LEFT JOIN lyrics_enriched le
    ON le.track_id = t.track_id
;
