"use client";

import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { MapContainer, Marker, Polyline, TileLayer, useMap } from "react-leaflet";
import { useEffect } from "react";
import type { GeneratedRoute } from "@/types/route";
import styles from "./RouteMap.module.css";

// Leaflet's default marker icons reference image files that don't resolve
// correctly under bundlers like webpack; rebuild them from CDN URLs.
const startIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

const endIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

interface Props {
  route: GeneratedRoute | null;
  fallbackCenter: [number, number];
}

function FitBounds({ route }: { route: GeneratedRoute }) {
  const map = useMap();
  useEffect(() => {
    const bounds = L.latLngBounds(route.route.map((c) => [c.latitude, c.longitude]));
    map.fitBounds(bounds, { padding: [32, 32] });
  }, [route, map]);
  return null;
}

export default function RouteMap({ route, fallbackCenter }: Props) {
  const center: [number, number] = route
    ? [route.start_latitude, route.start_longitude]
    : fallbackCenter;

  return (
    <div className={styles.mapWrapper}>
      <MapContainer center={center} zoom={14} style={{ width: "100%", height: "100%" }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {route && (
          <>
            <Polyline
              positions={route.route.map((c) => [c.latitude, c.longitude])}
              pathOptions={{ color: "#d98e2b", weight: 4, opacity: 0.9 }}
            />
            <Marker position={[route.start_latitude, route.start_longitude]} icon={startIcon} />
            <Marker position={[route.end_latitude, route.end_longitude]} icon={endIcon} />
            <FitBounds route={route} />
          </>
        )}
      </MapContainer>
    </div>
  );
}
