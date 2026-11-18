CREATE TABLE IF NOT EXISTS checkins(
  date TEXT PRIMARY KEY,
  body TEXT,
  sleep_felt TEXT,
  motivation INTEGER,
  time_available_min INTEGER,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions(
  id TEXT PRIMARY KEY,
  date TEXT,
  planned_session_id TEXT,
  location TEXT,
  status TEXT,
  session_rpe INTEGER,
  duration_min INTEGER,
  garmin_activity_id TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS sets(
  id TEXT PRIMARY KEY,
  session_id TEXT,
  date TEXT,
  exercise_id TEXT,
  set_no INTEGER,
  weight_kg REAL,
  reps INTEGER,
  rir INTEGER,
  estimated_1rm REAL
);

CREATE TABLE IF NOT EXISTS body_measures(
  date TEXT PRIMARY KEY,
  weight_kg REAL,
  waist_cm REAL
);

