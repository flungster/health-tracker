/** Leaflet map with the activity route drawn as a polyline. */

import { useMemo } from "react";
import { MapContainer, Polyline, TileLayer } from "react-leaflet";
import type { LatLngExpression } from "leaflet";

import type { TrackpointView } from "../api/types";
import { chartPalette } from "../theme/chartColors";
import { useTheme } from "../theme/context";

export default function RouteMap({ trackpoints }: { trackpoints: TrackpointView[] }) {
  const dark = useTheme().dark;
  const palette = chartPalette(dark);

  // Light theme: the standard OpenStreetMap tiles. Dark theme: CARTO's free
  // dark basemap (same OSM data, same tile-server class) so the map does not
  // glare inside a dark UI. The key forces Leaflet to swap layers cleanly.
  const tiles = dark
    ? {
        key: "carto-dark",
        url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      }
    : {
        key: "osm",
        url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      };

  const positions = useMemo<LatLngExpression[]>(() => {
    const result: LatLngExpression[] = [];
    for (const point of trackpoints) {
      if (point.lat !== null && point.lon !== null) {
        result.push([point.lat, point.lon]);
      }
    }
    return result;
  }, [trackpoints]);

  const bounds = useMemo(() => {
    if (positions.length === 0) {
      return null;
    }
    let minLat = 90;
    let maxLat = -90;
    let minLon = 180;
    let maxLon = -180;
    for (const position of positions) {
      const [lat, lon] = position as [number, number];
      minLat = Math.min(minLat, lat);
      maxLat = Math.max(maxLat, lat);
      minLon = Math.min(minLon, lon);
      maxLon = Math.max(maxLon, lon);
    }
    return [[minLat, minLon], [maxLat, maxLon]] as [[number, number], [number, number]];
  }, [positions]);

  const center = useMemo<[number, number]>(() => {
    if (positions.length === 0) {
      return [0, 0];
    }
    const first = positions[0] as [number, number];
    const last = positions[positions.length - 1] as [number, number];
    return [(first[0] + last[0]) / 2, (first[1] + last[1]) / 2];
  }, [positions]);

  return (
    <div className="h-80 overflow-hidden rounded-lg border border-line">
      <MapContainer
        center={center}
        bounds={bounds ?? undefined}
        boundsOptions={{ padding: [20, 20] }}
        scrollWheelZoom={false}
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer key={tiles.key} attribution={tiles.attribution} url={tiles.url} />
        <Polyline positions={positions} pathOptions={{ color: palette.accent, weight: 4 }} />
      </MapContainer>
    </div>
  );
}
