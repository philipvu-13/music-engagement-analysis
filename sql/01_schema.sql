-- Use the default schema
SET search_path TO public;

-- 1) Drop in the ONLY safe order (children first, then parents)
DROP TABLE IF EXISTS youtube_stats_snapshots;
DROP TABLE IF EXISTS youtube_videos;
DROP TABLE IF EXISTS lyrics;
DROP TABLE IF EXISTS tracks;

-- 2) Create tables in the correct order + match CSV column order

-- tracks.csv header:
-- track_id,track_number,track_name,track_name_raw
CREATE TABLE tracks (
  track_id TEXT PRIMARY KEY,
  track_number INT,
  track_name TEXT NOT NULL,
  track_name_raw TEXT
);

-- lyrics.csv header:
-- track_id,track_name,genius_url,lyrics,word_count,unique_word_count,repetition_ratio
CREATE TABLE lyrics (
  track_id TEXT PRIMARY KEY REFERENCES tracks(track_id),
  track_name TEXT,
  genius_url TEXT,
  lyrics TEXT,
  word_count INT,
  unique_word_count INT,
  repetition_ratio DOUBLE PRECISION
);

-- youtube_videos.csv header:
-- track_id,youtube_video_id,youtube_title,channel_title,published_at,is_official,match_confidence
CREATE TABLE youtube_videos (
  track_id TEXT REFERENCES tracks(track_id),
  youtube_video_id TEXT PRIMARY KEY,
  youtube_title TEXT,
  channel_title TEXT,
  published_at TIMESTAMP,
  is_official BOOLEAN,
  match_confidence TEXT
);

-- youtube_stats_snapshots.csv header:
-- youtube_video_id,captured_at,view_count,like_count,comment_count
CREATE TABLE youtube_stats_snapshots (
  youtube_video_id TEXT REFERENCES youtube_videos(youtube_video_id),
  captured_at TIMESTAMP NOT NULL,
  view_count BIGINT,
  like_count BIGINT,
  comment_count BIGINT,
  PRIMARY KEY (youtube_video_id, captured_at)
);
