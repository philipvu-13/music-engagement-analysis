SELECT
  repeat_bucket,
  AVG(window_engagement_score) AS avg_window_engagement_score,
  COUNT(*) AS track_count
FROM track_analysis_v
WHERE repeat_bucket IS NOT NULL
  AND window_engagement_score IS NOT NULL
GROUP BY repeat_bucket
ORDER BY avg_window_engagement_score DESC;
