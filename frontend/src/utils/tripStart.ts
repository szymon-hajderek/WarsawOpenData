/**
 * When an active trip really starts. A route found for a later departure opens the active trip in a waiting
 * state; GPS progress and the pace recording start at the departure time (or on "Ruszam teraz").
 */

/** A departure at most this far ahead starts at once. */
export const START_SLACK_S = 60;

/**
 * Full local date and time of a route's `departure` ("HH:MM").
 * `searchWhen` ("YYYY-MM-DDTHH:MM", the search's `when`) = the time the search was made for; without it the search
 * was for `now`. The departure is on that day, or the next one when it is more than 12 h before the searched time
 * (a trip found just before midnight).
 */
export function tripStartAt(departure: string, now: Date, searchWhen?: string | null): Date {
  const [h, m] = departure.split(':').map(Number);
  let base = now;
  if (searchWhen) {
    const [date, time] = searchWhen.split('T');
    const [y, mo, d] = date.split('-').map(Number);
    const [sh, sm] = (time ?? '00:00').split(':').map(Number);
    base = new Date(y, mo - 1, d, sh, sm, 0, 0);
  }
  const at = new Date(base.getFullYear(), base.getMonth(), base.getDate(), h, m, 0, 0);
  if (base.getTime() - at.getTime() > 12 * 3600_000) at.setDate(at.getDate() + 1);
  return at;
}

/** Whole seconds from `now` to `at` (negative when `at` is past). */
export const secondsUntil = (at: Date, now: Date): number => Math.ceil((at.getTime() - now.getTime()) / 1000);

/** The trip has to wait for its departure (more than a minute ahead). */
export const mustWait = (at: Date, now: Date): boolean => secondsUntil(at, now) > START_SLACK_S;

/** "za 23 min", "za 1 h 5 min", "za chwilę". */
export function countdownText(seconds: number): string {
  if (seconds < 60) return 'za chwilę';
  const min = Math.ceil(seconds / 60);
  if (min < 60) return `za ${min} min`;
  const h = Math.floor(min / 60);
  const rest = min % 60;
  return rest ? `za ${h} h ${rest} min` : `za ${h} h`;
}
