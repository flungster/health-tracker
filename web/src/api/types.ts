/** API response types, mirroring the backend view schemas. */

export type UserView = {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  created_at: string;
};

export type AuthResponseView = {
  user: UserView;
  token: string;
};

export type ProfileView = {
  max_heart_rate: number | null;
  resting_heart_rate: number | null;
};

export type ActivitySummaryView = {
  id: string;
  sport_type: string;
  name: string;
  started_at: string;
  duration_seconds: number;
  moving_seconds: number | null;
  distance_m: number | null;
  calories_kcal: number | null;
  elevation_gain_m: number | null;
  heart_rate_avg_bpm: number | null;
};

export type ActivitiesListView = {
  items: ActivitySummaryView[];
  total: number;
  limit: number;
  offset: number;
};

export type SplitView = {
  split_type: string;
  split_index: number;
  duration_seconds: number;
  pace_seconds: number;
  heart_rate_avg_bpm: number | null;
  cadence_avg_rpm: number | null;
};

export type SplitsView = {
  items: SplitView[];
};

export type HrZoneView = {
  zone_1_seconds: number;
  zone_2_seconds: number;
  zone_3_seconds: number;
  zone_4_seconds: number;
  zone_5_seconds: number;
};

export type RunningMetricsView = {
  avg_pace_s_per_km: number | null;
  min_pace_s_per_km: number | null;
  max_pace_s_per_km: number | null;
};

export type CyclingMetricsView = {
  power_avg_w: number | null;
  power_max_w: number | null;
};

export type RowingMetricsView = {
  stroke_rate_avg_spm: number | null;
  stroke_rate_min_spm: number | null;
  stroke_rate_max_spm: number | null;
  split_500m_seconds: number | null;
};

export type StrengthMetricsView = {
  total_sets: number;
  total_exercises: number;
  total_weight_kg: number | null;
};

export type ActivityDetailView = {
  id: string;
  sport_type: string;
  name: string;
  description: string | null;
  started_at: string;
  ended_at: string;
  duration_seconds: number;
  moving_seconds: number | null;
  distance_m: number | null;
  calories_kcal: number | null;
  elevation_gain_m: number | null;
  heart_rate_min_bpm: number | null;
  heart_rate_avg_bpm: number | null;
  heart_rate_max_bpm: number | null;
  cadence_avg_rpm: number | null;
  source_format: string | null;
  original_filename: string | null;
  created_at: string;
  splits: SplitView[];
  heart_rate_zones: HrZoneView | null;
  running: RunningMetricsView | null;
  cycling: CyclingMetricsView | null;
  rowing: RowingMetricsView | null;
  strength: StrengthMetricsView | null;
};

export type TrackpointView = {
  seq: number;
  recorded_at: string | null;
  lat: number | null;
  lon: number | null;
  altitude_m: number | null;
  heart_rate_bpm: number | null;
  cadence_rpm: number | null;
  speed_mps: number | null;
  power_w: number | null;
};

export type TrackpointsView = {
  items: TrackpointView[];
};

export type SportTypeView = {
  value: string;
  description: string;
};

export type SportsView = {
  sports: SportTypeView[];
};
