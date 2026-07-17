"use client";

import { useEffect } from "react";
import { MapContainer, TileLayer, CircleMarker, Polyline, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import type { SupplyChainMap } from "@/lib/types";

const KIND_COLOR: Record<string, string> = {
  site: "#f0b429",
  tier1: "#38bdf8",
  tier2: "#94a3b8",
};

// India-ish center so the initial view frames the domestic suppliers + site
// without needing a network geocoding call.
const CENTER: [number, number] = [20.5, 78.9];

export function SupplyChainMapView({ data }: { data: SupplyChainMap }) {
  useEffect(() => {
    // Leaflet reads window at import time; nothing to do here, this effect
    // just documents that this component is client-only (see dynamic import).
  }, []);

  return (
    <MapContainer
      center={CENTER}
      zoom={3}
      scrollWheelZoom={true}
      style={{ height: "100%", width: "100%", background: "#0B0F14" }}
    >
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://carto.com/attributions">CARTO</a> &copy; OpenStreetMap contributors'
      />
      {data.routes.map((r, i) => (
        <Polyline
          key={i}
          positions={[
            [r.from.lat, r.from.lon],
            [r.to.lat, r.to.lon],
          ]}
          pathOptions={{
            color: r.at_risk ? "#ef4444" : r.tier === 2 ? "#94a3b8" : "#38bdf8",
            weight: r.at_risk ? 2.5 : 1.5,
            opacity: r.at_risk ? 0.9 : 0.55,
            dashArray: r.tier === 2 ? "4 4" : undefined,
          }}
        />
      ))}
      {data.points.map((p) => (
        <CircleMarker
          key={p.id}
          center={[p.lat, p.lon]}
          radius={p.kind === "site" ? 8 : p.at_risk ? 7 : 5}
          pathOptions={{
            color: p.at_risk ? "#ef4444" : KIND_COLOR[p.kind],
            fillColor: p.at_risk ? "#ef4444" : KIND_COLOR[p.kind],
            fillOpacity: 0.85,
            weight: p.at_risk ? 2 : 1,
          }}
        >
          <Tooltip direction="top" offset={[0, -6]}>
            <span style={{ fontFamily: "monospace", fontSize: "0.7rem" }}>
              {p.kind === "site" ? "Project site" : p.label} · {p.city}
              {p.at_risk ? " · AT RISK" : ""}
              {p.equipment_spec_status === "MATCH" && " · spec ✓ IS 8623-1"}
              {p.equipment_spec_status === "MISMATCH" && " · spec MISMATCH (IS 8623-1)"}
            </span>
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
