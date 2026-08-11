"use client";

import { useEffect, useState } from "react";
import type { Algorithm, RouteRequest, RouteType } from "@/types/route";
import styles from "./InputPanel.module.css";

interface Props {
  onSubmit: (request: RouteRequest) => void;
  isLoading: boolean;
  errorMessage: string | null;
  selectedLatitude: number;
  selectedLongitude: number;
}

export default function InputPanel({
  onSubmit,
  isLoading,
  errorMessage,
  selectedLatitude,
  selectedLongitude,
}: Props) {
  const [latitude, setLatitude] = useState(selectedLatitude.toFixed(5));
  const [longitude, setLongitude] = useState(selectedLongitude.toFixed(5));

  // Clicking the map (see RouteMap) updates selectedLatitude/Longitude in
  // the parent; mirror that into these text fields without fighting the
  // user's own typing (this effect only fires when the *props* change).
  useEffect(() => {
    setLatitude(selectedLatitude.toFixed(5));
  }, [selectedLatitude]);

  useEffect(() => {
    setLongitude(selectedLongitude.toFixed(5));
  }, [selectedLongitude]);

  const [targetDistance, setTargetDistance] = useState("5");
  const [elevationGain, setElevationGain] = useState("300");
  const [pace, setPace] = useState("10");
  const [routeType, setRouteType] = useState<RouteType>("loop");
  const [algorithm, setAlgorithm] = useState<Algorithm>("astar");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      latitude: parseFloat(latitude),
      longitude: parseFloat(longitude),
      target_distance_miles: parseFloat(targetDistance),
      desired_elevation_gain_ft: parseFloat(elevationGain),
      pace_min_per_mile: parseFloat(pace),
      route_type: routeType,
      algorithm,
    });
  }

  return (
    <form className={styles.panel} onSubmit={handleSubmit}>
      <div>
        <p className={styles.eyebrow}>Route parameters</p>
        <h1 className={styles.title}>Plan a run</h1>
      </div>

      <span className={styles.hint}>Click anywhere on the map to set your start point.</span>

      <div className={styles.row}>
        <div className={styles.field}>
          <label className={styles.label} htmlFor="latitude">
            Start latitude
          </label>
          <input
            id="latitude"
            className={styles.input}
            type="number"
            step="0.0001"
            value={latitude}
            onChange={(e) => setLatitude(e.target.value)}
            required
          />
        </div>
        <div className={styles.field}>
          <label className={styles.label} htmlFor="longitude">
            Start longitude
          </label>
          <input
            id="longitude"
            className={styles.input}
            type="number"
            step="0.0001"
            value={longitude}
            onChange={(e) => setLongitude(e.target.value)}
            required
          />
        </div>
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="distance">
          Target distance (miles)
        </label>
        <input
          id="distance"
          className={styles.input}
          type="number"
          min="0.5"
          max="15"
          step="0.1"
          value={targetDistance}
          onChange={(e) => setTargetDistance(e.target.value)}
          required
        />
        <span className={styles.hint}>0.5–15 miles</span>
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="elevation">
          Desired elevation gain (ft)
        </label>
        <input
          id="elevation"
          className={styles.input}
          type="number"
          min="0"
          max="3000"
          step="10"
          value={elevationGain}
          onChange={(e) => setElevationGain(e.target.value)}
          required
        />
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="pace">
          Your pace (min/mile)
        </label>
        <input
          id="pace"
          className={styles.input}
          type="number"
          min="3"
          max="60"
          step="0.5"
          value={pace}
          onChange={(e) => setPace(e.target.value)}
          required
        />
        <span className={styles.hint}>Used to personalize the time estimate (default: 10 min/mile).</span>
      </div>

      <div className={styles.field}>
        <span className={styles.label}>Route type</span>
        <div className={styles.segmented}>
          <button
            type="button"
            className={`${styles.segmentedOption} ${
              routeType === "loop" ? styles.segmentedOptionActive : ""
            }`}
            onClick={() => setRouteType("loop")}
          >
            Loop
          </button>
          <button
            type="button"
            className={`${styles.segmentedOption} ${
              routeType === "out_and_back" ? styles.segmentedOptionActive : ""
            }`}
            onClick={() => setRouteType("out_and_back")}
          >
            Out &amp; back
          </button>
        </div>
      </div>

      <div className={styles.field}>
        <span className={styles.label}>Algorithm</span>
        <div className={styles.segmented}>
          <button
            type="button"
            className={`${styles.segmentedOption} ${
              algorithm === "astar" ? styles.segmentedOptionActive : ""
            }`}
            onClick={() => setAlgorithm("astar")}
          >
            A*
          </button>
          <button
            type="button"
            className={`${styles.segmentedOption} ${
              algorithm === "dijkstra" ? styles.segmentedOptionActive : ""
            }`}
            onClick={() => setAlgorithm("dijkstra")}
          >
            Dijkstra
          </button>
        </div>
      </div>

      {errorMessage && <div className={styles.errorBox}>{errorMessage}</div>}

      <button className={styles.submit} type="submit" disabled={isLoading}>
        {isLoading ? "Generating route…" : "Generate route"}
      </button>
    </form>
  );
}
