SELECT
  track_number,
  track_name,
  word_count,
  window_engagement_score,
  word_count_bucket,
  views_delta_per_day
FROM track_analysis_v
WHERE word_count IS NOT NULL
  AND window_engagement_score IS NOT NULL
ORDER BY track_number;
