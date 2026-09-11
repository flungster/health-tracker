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
  date_of_birth: string | null; // "YYYY-MM-DD" (calendar day)
  custom_zone_1_top_bpm: number | null;
  custom_zone_2_top_bpm: number | null;
  custom_zone_3_top_bpm: number | null;
  custom_zone_4_top_bpm: number | null;

  // Computed (not stored): the zone reference currently in effect.
  zone_source: "custom" | "max_heart_rate" | "age" | null;
  effective_max_heart_rate: number | null; // for max_heart_rate / age references
  age: number | null; // when zone_source is "age"

  /** Derived display unit system (never null). */
  units_system: "metric" | "imperial";
};

/** The display unit system a response's unit-bearing values are expressed in. */
export type Units = "metric" | "imperial";

/** Unit-bearing activity values are in the caller's display system (see `units`). */
export type ActivitySummaryView = {
  id: string;
  sport_type: string;
  name: string;
  started_at: string;
  duration_seconds: number;
  moving_seconds: number | null;
  distance: number | null; // meters when units is "metric", miles otherwise
  calories_kcal: number | null;
  elevation_gain: number | null; // meters when "metric", feet otherwise
  heart_rate_avg_bpm: number | null;
  /** e.g. "strava"; null for file imports (M21 provenance). */
  provider: string | null;
};

export type ActivitiesListView = {
  items: ActivitySummaryView[];
  total: number;
  limit: number;
  offset: number;
  units: Units; // display system of all unit-bearing values in this response
};

/** Aggregate stats for one user's activities over a period (dashboard). */
export type ActivityPeriodSummaryView = {
  units: Units; // display system of all unit-bearing values in this response
  activity_count: {
    total: number; // always a number (0 for an empty period)
    by_sport_type: Record<string, number>; // only sports with ≥ 1 activity
  };
  moving_seconds_total: number | null; // null when no activity has a moving time
  distance: number | null; // meters when "metric", miles otherwise
  elevation_gain: number | null; // meters when "metric", feet otherwise
  calories_kcal: number | null; // universal — never converted
  avg_heart_rate_bpm: number | null; // mean of the per-activity averages
  weight_lifted: number | null; // kg when "metric", lb otherwise (strength volume)
  /** Empty list = the period has no distance data at all. */
  distance_trend: { start: string; value: number }[]; // `value` follows `units`
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
  /** Pace in seconds per display distance unit (km when metric, mi otherwise). */
  avg_pace_seconds: number | null;
  min_pace_seconds: number | null;
  max_pace_seconds: number | null;
};

export type WalkingMetricsView = {
  /** Pace in seconds per display distance unit (km when metric, mi otherwise). */
  avg_pace_seconds: number | null;
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
  /** kg when units is "metric", lb otherwise. */
  total_weight: number | null;
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
  distance: number | null; // meters when units is "metric", miles otherwise
  calories_kcal: number | null;
  elevation_gain: number | null; // meters when "metric", feet otherwise
  heart_rate_min_bpm: number | null;
  heart_rate_avg_bpm: number | null;
  heart_rate_max_bpm: number | null;
  cadence_avg_rpm: number | null;
  /** e.g. "strava"; null for file imports (M21 provenance). */
  provider: string | null;
  source_format: string | null; // e.g. "gpx"; null when fetched from a provider
  original_filename: string | null; // uploaded file name; null for provider fetches
  created_at: string;
  units: Units; // display system of all unit-bearing values in this response
  /** Splits already filtered to `units` (km rows for metric, mi rows otherwise). */
  splits: SplitView[];
  heart_rate_zones: HrZoneView | null;
  running: RunningMetricsView | null;
  walking: WalkingMetricsView | null;
  cycling: CyclingMetricsView | null;
  rowing: RowingMetricsView | null;
  strength: StrengthMetricsView | null;
};

export type TrackpointView = {
  seq: number;
  recorded_at: string | null;
  lat: number | null;
  lon: number | null;
  altitude: number | null; // meters when units is "metric", feet otherwise
  heart_rate_bpm: number | null;
  cadence_rpm: number | null;
  speed: number | null; // m/s when "metric", mph otherwise
  power_w: number | null;
};

export type TrackpointsView = {
  items: TrackpointView[];
  units: Units; // display system of altitude/speed in this response
};

export type ActivityImageView = {
  id: string; // public uuid of the image row (used in URLs)
  source: string; // e.g. "uploaded"
  original_filename: string | null;
  bytes: number; // file size in bytes (display)
  created_at: string; // ISO 8601 UTC upload time
};

export type ActivityImagesView = {
  items: ActivityImageView[]; // upload order
};

export type SportTypeView = {
  value: string;
  description: string;
};

export type SportsView = {
  sports: SportTypeView[];
};

export type ProviderInfoView = {
  value: string;
  description: string;
  configured: boolean;
};

export type ProvidersView = {
  providers: ProviderInfoView[];
};

export type ConnectUrlView = {
  url: string;
};

export type ProviderConnectionView = {
  provider: string;
  external_user_id: string;
  display_name: string | null;
  connected_at: string;
  last_sync_at: string | null;
  /** The import-from floor (ISO 8601 UTC), or null = import everything. */
  sync_since: string | null;
};

export type ClientConfigView = {
  provider: string;
  configured: boolean;
  client_id: string | null;
  display_name: string | null;
};

export type SyncResultView = {
  imported: number;
  skipped: number;
  last_sync_at: string;
};
