/**
 * Departure time of a search. `null` = now (no `when` is sent); otherwise a Warsaw local datetime
 * `YYYY-MM-DDTHH:MM`, sent as `when` to `POST /api/routes` as it is.
 */
export type Departure = string | null;

const pad = (n: number) => String(n).padStart(2, '0');

/** `YYYY-MM-DD` of a local date. */
export const dateKey = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** `HH:MM` of a local date. */
export const timeKey = (d: Date) => `${pad(d.getHours())}:${pad(d.getMinutes())}`;

/** The day after `d` (local). */
export const nextDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1);

/** `YYYY-MM-DDTHH:MM` from a date key and a time key. */
export const makeDeparture = (date: string, time: string): Departure => `${date}T${time}`;

/** The `when` of the request: nothing for now. */
export const departureWhen = (d: Departure): string | undefined => d ?? undefined;

/** "dziś 14:30", "jutro 08:00", "20.10 08:00"; `null` for now. */
function dayAndTime(d: Departure, now: Date): string | null {
  if (!d) return null;
  const [date, time] = d.split('T');
  if (date === dateKey(now)) return `dziś ${time}`;
  if (date === dateKey(nextDay(now))) return `jutro ${time}`;
  const [, month, day] = date.split('-');
  return `${day}.${month} ${time}`;
}

/** Label of the control: "Wyjazd: Teraz", "Wyjazd: dziś 14:30", "Wyjazd: jutro 08:00", "Wyjazd: 20.10 08:00". */
export function departureLabel(d: Departure, now: Date = new Date()): string {
  return `Wyjazd: ${dayAndTime(d, now) ?? 'Teraz'}`;
}

/** Header text of the route list: "Wyjazd 14:30", "Wyjazd jutro 08:00", "Wyjazd 20.10 08:00"; `null` for now. */
export function departureSummary(d: Departure, now: Date = new Date()): string | null {
  const text = dayAndTime(d, now);
  if (!text) return null;
  return `Wyjazd ${text.replace(/^dziś /, '')}`;
}

/** True when the chosen departure has already passed (shown muted; the search still runs). */
export function isPastDeparture(d: Departure, now: Date = new Date()): boolean {
  if (!d) return false;
  return d < `${dateKey(now)}T${timeKey(now)}`;
}
