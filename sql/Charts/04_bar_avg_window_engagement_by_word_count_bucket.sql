SELECT
  word_count_bucket,
  AVG(window_engagement_score) AS avg_window_engagement_score,
  COUNT(*) AS track_count
FROM track_analysis_v
WHERE word_count_bucket IS NOT NULL
  AND window_engagement_score IS NOT NULL
GROUP BY word_count_bucket
ORDER BY
  CASE word_count_bucket
    WHEN '0–200' THEN 1
    WHEN '201–400' THEN 2
    WHEN '401+' THEN 3
    ELSE 99
  END;
