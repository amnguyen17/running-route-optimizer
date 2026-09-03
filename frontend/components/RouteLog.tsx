"use client";

import { useEffect, useState } from "react";
import { ApiRequestError, deleteSavedRoute, getSavedRoute, listSavedRoutes, setRouteFavorite } from "@/lib/api";
import type { SavedRouteDetail, SavedRouteSummary } from "@/types/route";
import styles from "./RouteLog.module.css";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onLoadRoute: (detail: SavedRouteDetail) => void;
  refreshToken: number;
}

export default function RouteLog({ isOpen, onClose, onLoadRoute, refreshToken }: Props) {
  const [routes, setRoutes] = useState<SavedRouteSummary[]>([]);
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<number | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    listSavedRoutes(favoritesOnly)
      .then((result) => {
        if (!cancelled) setRoutes(result);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiRequestError ? err.message : "Failed to load the route log.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, favoritesOnly, refreshToken]);

  async function handleToggleFavorite(id: number, current: boolean) {
    setPendingId(id);
    try {
      const updated = await setRouteFavorite(id, !current);
      setRoutes((prev) =>
        favoritesOnly && !updated.is_favorite
          ? prev.filter((r) => r.id !== id)
          : prev.map((r) => (r.id === id ? updated : r))
      );
    } catch {
      setError("Failed to update favorite status.");
    } finally {
      setPendingId(null);
    }
  }

  async function handleDelete(id: number) {
    setPendingId(id);
    try {
      await deleteSavedRoute(id);
      setRoutes((prev) => prev.filter((r) => r.id !== id));
    } catch {
      setError("Failed to delete this route.");
    } finally {
      setPendingId(null);
    }
  }

  async function handleView(id: number) {
    setPendingId(id);
    try {
      const detail = await getSavedRoute(id);
      onLoadRoute(detail);
      onClose();
    } catch {
      setError("Failed to load this route.");
    } finally {
      setPendingId(null);
    }
  }

  if (!isOpen) return null;

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <aside className={styles.panel} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2 className={styles.title}>Route log</h2>
          <button type="button" className={styles.closeButton} onClick={onClose} aria-label="Close route log">
            ✕
          </button>
        </div>

        <div className={styles.filterRow}>
          <button
            type="button"
            className={`${styles.filterOption} ${!favoritesOnly ? styles.filterOptionActive : ""}`}
            onClick={() => setFavoritesOnly(false)}
          >
            All
          </button>
          <button
            type="button"
            className={`${styles.filterOption} ${favoritesOnly ? styles.filterOptionActive : ""}`}
            onClick={() => setFavoritesOnly(true)}
          >
            ★ Favorites
          </button>
        </div>

        {error && <div className={styles.errorBox}>{error}</div>}

        {isLoading && <div className={styles.emptyState}>Loading…</div>}

        {!isLoading && routes.length === 0 && (
          <div className={styles.emptyState}>
            {favoritesOnly ? "No favorite routes yet." : "No saved routes yet. Generate a route and save it here."}
          </div>
        )}

        <ul className={styles.list}>
          {routes.map((r) => (
            <li key={r.id} className={styles.entry}>
              <button
                type="button"
                className={styles.starButton}
                onClick={() => handleToggleFavorite(r.id, r.is_favorite)}
                disabled={pendingId === r.id}
                aria-label={r.is_favorite ? "Unfavorite this route" : "Favorite this route"}
                title={r.is_favorite ? "Unfavorite" : "Favorite"}
              >
                {r.is_favorite ? "★" : "☆"}
              </button>

              <div className={styles.entryBody} onClick={() => handleView(r.id)}>
                <div className={styles.entryTop}>
                  <span className={styles.entryDistance}>{r.distance_miles.toFixed(2)} mi</span>
                  <span className={styles.entryDate}>{formatDate(r.created_at)}</span>
                </div>
                <div className={styles.entryMeta}>
                  {Math.round(r.elevation_gain_ft)} ft gain · {r.route_type === "loop" ? "Loop" : "Out & back"} ·{" "}
                  {r.algorithm === "astar" ? "A*" : "Dijkstra"}
                </div>
              </div>

              <button
                type="button"
                className={styles.deleteButton}
                onClick={() => handleDelete(r.id)}
                disabled={pendingId === r.id}
                aria-label="Delete this saved route"
                title="Delete"
              >
                🗑
              </button>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
