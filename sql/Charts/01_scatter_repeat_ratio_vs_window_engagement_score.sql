SELECT
  track_name,
  repeat_ratio,
  window_engagement_score,
  repeat_bucket,
  views_delta_per_day
FROM track_analysis_v
WHERE repeat_ratio IS NOT NULL
  AND window_engagement_score IS NOT NULL;
