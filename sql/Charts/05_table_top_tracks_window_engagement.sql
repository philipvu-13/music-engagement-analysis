SELECT
  track_number,
  track_name,

  -- Window engagement (your snapshot period)
  window_engagement_score,
  window_engagement_rate,

  -- Window growth / momentum
  views_delta,
  views_delta_per_day,
  likes_delta,
  comments_delta,

  -- "As-of" totals (end of window)
  views,
  likes,
  comments,

  -- Lyrics metrics
  word_count,
  word_count_bucket,
  repeat_ratio,
  repeat_bucket,
  lexical_diversity,

  -- Cross-domain bridge metric (optional but strong)
  engagement_per_100_words

FROM track_analysis_v
WHERE window_engagement_score IS NOT NULL
ORDER BY window_engagement_score DESC;
