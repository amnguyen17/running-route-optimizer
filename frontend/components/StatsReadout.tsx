import type { GeneratedRoute } from "@/types/route";
import styles from "./StatsReadout.module.css";

interface Props {
  route: GeneratedRoute | null;
}

export default function StatsReadout({ route }: Props) {
  if (!route) {
    return (
      <div className={styles.emptyState}>
        Generate a route to see distance, elevation, and pace statistics here.
      </div>
    );
  }

  const time = formatMinutes(route.estimated_time_minutes);

  return (
    <div className={styles.readout}>
      {!route.elevation_available && (
        <div className={styles.emptyState}>
          Elevation data was unavailable for this route — gain/loss/difficulty below are not
          meaningful (shown as 0).
        </div>
      )}
      <Stat label="Distance" value={route.distance_miles.toFixed(2)} unit="mi" />
      <Stat label="Elevation gain" value={Math.round(route.elevation_gain_ft)} unit="ft" />
      <Stat label="Elevation loss" value={Math.round(route.elevation_loss_ft)} unit="ft" />
      <Stat label="Est. time" value={time} unit="" />
      <Stat label="Algorithm" value={route.algorithm === "astar" ? "A*" : "Dijkstra"} unit="" />
      <Stat label="Score" value={route.score.toFixed(3)} unit="" />
      <div className={styles.stat}>
        <span className={styles.statLabel}>Difficulty</span>
        <span className={styles.statValue}>{(route.difficulty * 100).toFixed(0)}</span>
        <div className={styles.difficultyBar}>
          <div
            className={styles.difficultyFill}
            style={{ width: `${Math.min(100, route.difficulty * 100)}%` }}
          />
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, unit }: { label: string; value: string | number; unit: string }) {
  return (
    <div className={styles.stat}>
      <span className={styles.statLabel}>{label}</span>
      <span className={styles.statValue}>
        {value}
        {unit && <span className={styles.statUnit}>{unit}</span>}
      </span>
    </div>
  );
}

function formatMinutes(totalMinutes: number): string {
  const minutes = Math.floor(totalMinutes);
  const seconds = Math.round((totalMinutes - minutes) * 60);
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}
