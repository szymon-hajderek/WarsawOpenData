export function formatDuration(min: number): string {
  const total = Math.max(1, Math.round(min));
  if (total < 60) return `${total} min`;
  const h = Math.floor(total / 60);
  const m = total % 60;
  return m === 0 ? `${h} h` : `${h} h ${String(m).padStart(2, '0')} min`;
}

export function formatDistance(m: number): string {
  if (m < 1000) return `${Math.round(m / 10) * 10} m`;
  return `${(m / 1000).toFixed(1).replace('.', ',')} km`;
}

export function formatTime(date: Date): string {
  return date.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
}

export function transfersLabel(n: number): string {
  if (n === 0) return 'bez przesiadek';
  if (n === 1) return '1 przesiadka';
  if (n >= 2 && n <= 4) return `${n} przesiadki`;
  return `${n} przesiadek`;
}

/** "1 przystanek", "2 przystanki", "5 przystanków". */
export function stopsLabel(n: number): string {
  if (n === 1) return '1 przystanek';
  if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14)) return `${n} przystanki`;
  return `${n} przystanków`;
}
