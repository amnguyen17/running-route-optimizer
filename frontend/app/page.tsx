"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import InputPanel from "@/components/InputPanel";
import RouteLog from "@/components/RouteLog";
import StatsReadout, { type SaveState } from "@/components/StatsReadout";
import ThemeToggle from "@/components/ThemeToggle";
import { ApiRequestError, generateRoute, saveRoute } from "@/lib/api";
import type { GeneratedRoute, RouteRequest, SavedRouteDetail } from "@/types/route";
import styles from "./page.module.css";

// Leaflet touches `window` at import time, so the map must be loaded
// client-side only.
const RouteMap = dynamic(() => import("@/components/RouteMap"), {
  ssr: false,
  loading: () => <div style={{ padding: 24 }}>Loading map…</div>,
});

const DEFAULT_CENTER: [number, number] = [37.2296, -80.4139]; // Blacksburg, VA

export default function Home() {
  const [route, setRoute] = useState<GeneratedRoute | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [startPoint, setStartPoint] = useState<[number, number]>(DEFAULT_CENTER);
  const [paceUsed, setPaceUsed] = useState(10);
  const [lastRequest, setLastRequest] = useState<RouteRequest | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [isLogOpen, setIsLogOpen] = useState(false);
  const [logRefreshToken, setLogRefreshToken] = useState(0);

  async function handleSubmit(request: RouteRequest) {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const result = await generateRoute(request);
      setRoute(result);
      setPaceUsed(request.pace_min_per_mile);
      setLastRequest(request);
      setSaveState("idle");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("Something went wrong generating this route. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSaveRoute() {
    if (!lastRequest) return;
    setSaveState("saving");
    try {
      await saveRoute(lastRequest);
      setSaveState("saved");
      setLogRefreshToken((t) => t + 1);
    } catch {
      setSaveState("error");
    }
  }

  function handleLoadRoute(detail: SavedRouteDetail) {
    const loaded = savedRouteToGeneratedRoute(detail);
    setRoute(loaded);
    setStartPoint([loaded.start_latitude, loaded.start_longitude]);
    setPaceUsed(loaded.average_pace_min_per_mile);
    setLastRequest(null);
    setSaveState("saved");
    setErrorMessage(null);
  }

  function handleSelectStart(lat: number, lon: number) {
    setStartPoint([lat, lon]);
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <ContourBackground />
        <div className={styles.headerInner}>
          <span className={styles.brand}>
            Running Route <span className={styles.brandAccent}>Optimizer</span>
          </span>
          <span className={styles.tagline}>OSM graph · Dijkstra / A* · elevation-aware scoring</span>
          <button type="button" className={styles.logButton} onClick={() => setIsLogOpen(true)}>
            Route Log
          </button>
          <ThemeToggle />
        </div>
      </header>

      <main className={styles.main}>
        <InputPanel
          onSubmit={handleSubmit}
          isLoading={isLoading}
          errorMessage={errorMessage}
          selectedLatitude={startPoint[0]}
          selectedLongitude={startPoint[1]}
        />

        <div className={styles.mapColumn}>
          <StatsReadout
            route={route}
            paceMinPerMile={paceUsed}
            onSave={lastRequest ? handleSaveRoute : undefined}
            saveState={saveState}
          />
          <div className={styles.mapArea}>
            <RouteMap
              route={route}
              fallbackCenter={DEFAULT_CENTER}
              selectedStart={startPoint}
              onSelectStart={handleSelectStart}
            />
          </div>
        </div>
      </main>

      <RouteLog
        isOpen={isLogOpen}
        onClose={() => setIsLogOpen(false)}
        onLoadRoute={handleLoadRoute}
        refreshToken={logRefreshToken}
      />
    </div>
  );
}

function savedRouteToGeneratedRoute(detail: SavedRouteDetail): GeneratedRoute {
  const first = detail.route[0];
  const last = detail.route[detail.route.length - 1];
  return {
    route: detail.route,
    distance_miles: detail.distance_miles,
    elevation_gain_ft: detail.elevation_gain_ft,
    elevation_loss_ft: detail.elevation_loss_ft,
    estimated_time_minutes: detail.estimated_time_minutes,
    average_pace_min_per_mile:
      detail.distance_miles > 0 ? detail.estimated_time_minutes / detail.distance_miles : 0,
    difficulty: detail.difficulty,
    algorithm: detail.algorithm,
    score: detail.score,
    start_latitude: first?.latitude ?? 0,
    start_longitude: first?.longitude ?? 0,
    end_latitude: last?.latitude ?? 0,
    end_longitude: last?.longitude ?? 0,
    elevation_available: true,
  };
}

function ContourBackground() {
  // A quiet topographic contour-line motif -- the page's one signature
  // element, kept subtle (low opacity, background layer only) so it
  // doesn't compete with the functional UI in front of it.
  return (
    <svg
      className={styles.headerContour}
      viewBox="0 0 800 120"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {[0, 1, 2, 3].map((i) => (
        <path
          key={i}
          d={`M0,${30 + i * 22} C150,${10 + i * 22} 250,${55 + i * 22} 400,${30 + i * 22} C550,${5 + i * 22} 650,${55 + i * 22} 800,${25 + i * 22}`}
          fill="none"
          stroke="#3f6b52"
          strokeOpacity={0.12 + i * 0.03}
          strokeWidth="1.5"
        />
      ))}
    </svg>
  );
}
