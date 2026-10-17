import type { LatLng } from '../types';

const EARTH_RADIUS_M = 6371000;
const toRad = (deg: number) => (deg * Math.PI) / 180;

export function haversine(a: LatLng, b: LatLng): number {
  const dLat = toRad(b[0] - a[0]);
  const dLng = toRad(b[1] - a[1]);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a[0])) * Math.cos(toRad(b[0])) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h));
}

const lerp = (a: LatLng, b: LatLng, t: number): LatLng => [
  a[0] + (b[0] - a[0]) * t,
  a[1] + (b[1] - a[1]) * t,
];

/**
 * Street-like curve between two points (used by the mock routing service until
 * OpenTripPlanner provides real geometry).
 */
export function buildPath(a: LatLng, b: LatLng, bend: number, phase: number, points = 48): LatLng[] {
  const dLat = b[0] - a[0];
  const dLng = b[1] - a[1];
  const k = Math.cos(toRad(a[0]));
  const path: LatLng[] = [];
  for (let i = 0; i <= points; i++) {
    const t = i / points;
    const amp = bend * Math.sin(Math.PI * t) * (1 + 0.4 * Math.sin(4 * Math.PI * t + phase));
    const base = lerp(a, b, t);
    path.push([base[0] + amp * dLng * k, base[1] - (amp * dLat) / k]);
  }
  return path;
}

/** Part of a path between two fractions (0..1) of its total length. */
export function slicePath(path: LatLng[], from: number, to: number): LatLng[] {
  const cum = [0];
  for (let i = 1; i < path.length; i++) cum.push(cum[i - 1] + haversine(path[i - 1], path[i]));
  const total = cum[cum.length - 1];

  const at = (d: number): LatLng => {
    let i = 1;
    while (i < cum.length - 1 && cum[i] < d) i++;
    const seg = cum[i] - cum[i - 1] || 1;
    return lerp(path[i - 1], path[i], (d - cum[i - 1]) / seg);
  };

  const d0 = from * total;
  const d1 = to * total;
  const out: LatLng[] = [at(d0)];
  for (let i = 0; i < path.length; i++) {
    if (cum[i] > d0 && cum[i] < d1) out.push(path[i]);
  }
  out.push(at(d1));
  return out;
}
