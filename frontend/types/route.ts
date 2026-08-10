export type RouteType = "loop" | "out_and_back";
export type Algorithm = "dijkstra" | "astar";

export interface RouteRequest {
  latitude: number;
  longitude: number;
  target_distance_miles: number;
  desired_elevation_gain_ft: number;
  max_elevation_gain_ft?: number;
  route_type: RouteType;
  algorithm: Algorithm;
}

export interface RouteCoordinate {
  latitude: number;
  longitude: number;
  elevation_m: number | null;
}

export interface GeneratedRoute {
  route: RouteCoordinate[];
  distance_miles: number;
  elevation_gain_ft: number;
  elevation_loss_ft: number;
  estimated_time_minutes: number;
  average_pace_min_per_mile: number;
  difficulty: number;
  algorithm: string;
  score: number;
  start_latitude: number;
  start_longitude: number;
  end_latitude: number;
  end_longitude: number;
  elevation_available: boolean;
}

export interface SavedRouteSummary {
  id: number;
  created_at: string;
  target_distance_miles: number;
  desired_elevation_gain_ft: number;
  route_type: string;
  algorithm: string;
  distance_miles: number;
  elevation_gain_ft: number;
  elevation_loss_ft: number;
  estimated_time_minutes: number;
  difficulty: number;
  score: number;
}

export interface ApiError {
  detail: string;
}
