WITH top_tracks AS (
  -- Use the VIEW (your exported spreadsheet) to choose the top 5 tracks
  SELECT
    track_id,
    track_name,
    primary_video_id,
    window_start_at,
    window_end_at
  FROM track_analysis_v
  WHERE primary_video_id IS NOT NULL
    AND window_start_at IS NOT NULL
    AND window_end_at IS NOT NULL
  ORDER BY views_delta_per_day DESC
  LIMIT 5
),
snap AS (
  -- Pull snapshots ONLY for those primary videos (again, driven by the VIEW)
  SELECT
    s.youtube_video_id,
    s.captured_at,
    s.view_count,
    t.track_name,
    t.window_start_at,
    t.window_end_at,
    LAG(s.view_count) OVER (
      PARTITION BY s.youtube_video_id
      ORDER BY s.captured_at
    ) AS prev_view_count,
    LAG(s.captured_at) OVER (
      PARTITION BY s.youtube_video_id
      ORDER BY s.captured_at
    ) AS prev_captured_at
  FROM youtube_stats_snapshots s
  JOIN top_tracks t
    ON t.primary_video_id = s.youtube_video_id
  WHERE s.captured_at >= (SELECT MIN(window_start_at) FROM top_tracks)
    AND s.captured_at <= (SELECT MAX(window_end_at) FROM top_tracks)
)
SELECT
  captured_at,                 -- use timestamp (not ::date) for accuracy
  track_name,
  (view_count - prev_view_count) AS views_gained,
  (view_count - prev_view_count)::numeric
    / NULLIF(EXTRACT(EPOCH FROM (captured_at - prev_captured_at)) / 86400.0, 0)
    AS views_gained_per_day
FROM snap
WHERE prev_view_count IS NOT NULL
ORDER BY captured_at, track_name;
