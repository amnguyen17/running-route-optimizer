"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import InputPanel from "@/components/InputPanel";
import StatsReadout from "@/components/StatsReadout";
import { ApiRequestError, generateRoute } from "@/lib/api";
import type { GeneratedRoute, RouteRequest } from "@/types/route";
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

  async function handleSubmit(request: RouteRequest) {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const result = await generateRoute(request);
      setRoute(result);
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

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <ContourBackground />
        <div className={styles.headerInner}>
          <span className={styles.brand}>
            Running Route <span className={styles.brandAccent}>Optimizer</span>
          </span>
          <span className={styles.tagline}>OSM graph · Dijkstra / A* · elevation-aware scoring</span>
        </div>
      </header>

      <main className={styles.main}>
        <InputPanel onSubmit={handleSubmit} isLoading={isLoading} errorMessage={errorMessage} />

        <div className={styles.mapColumn}>
          <StatsReadout route={route} />
          <div className={styles.mapArea}>
            <RouteMap route={route} fallbackCenter={DEFAULT_CENTER} />
          </div>
        </div>
      </main>
    </div>
  );
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
