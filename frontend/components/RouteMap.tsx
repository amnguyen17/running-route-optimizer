"use client";

import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { MapContainer, Marker, Polyline, TileLayer, useMap, useMapEvents } from "react-leaflet";
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

const selectedIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

interface Props {
  route: GeneratedRoute | null;
  fallbackCenter: [number, number];
  selectedStart: [number, number];
  onSelectStart: (lat: number, lon: number) => void;
}

function ClickToSetStart({ onSelectStart }: { onSelectStart: (lat: number, lon: number) => void }) {
  useMapEvents({
    click(e) {
      onSelectStart(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function FitBounds({ route }: { route: GeneratedRoute }) {
  const map = useMap();
  useEffect(() => {
    const bounds = L.latLngBounds(route.route.map((c) => [c.latitude, c.longitude]));
    map.fitBounds(bounds, { padding: [32, 32] });
  }, [route, map]);
  return null;
}

export default function RouteMap({ route, fallbackCenter, selectedStart, onSelectStart }: Props) {
  const center: [number, number] = route
    ? [route.start_latitude, route.start_longitude]
    : fallbackCenter;

  // Once a route exists, its own green start marker shows the start point
  // -- only show the separate "selected" pin if the user has since clicked
  // a new point that hasn't been generated into a route yet.
  const showSelectedPin =
    !route || route.start_latitude !== selectedStart[0] || route.start_longitude !== selectedStart[1];

  return (
    <div className={styles.mapWrapper}>
      <MapContainer center={center} zoom={14} style={{ width: "100%", height: "100%" }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ClickToSetStart onSelectStart={onSelectStart} />
        {showSelectedPin && <Marker position={selectedStart} icon={selectedIcon} />}
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
