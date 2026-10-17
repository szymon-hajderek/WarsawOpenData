import type { LatLng, RouteOption, TransportMode } from '../types';
import type { SpeedMode, SpeedSummary } from '../history/types';

/**
 * Preferences and trip filters (UI model only: choosing routes from them is the backend's job).
 * - `Preferences`: the user's saved settings (the default basis for choosing routes).
 * - `TimeRule`: hours in which some preferences change (e.g. "Noc").
 * - `TripFilters`: changes for one search only (sorting, allowed modes, overrides of the preferences).
 */

// ---------------------------------------------------------------- districts

export const DISTRICTS = [
  'Bemowo',
  'Białołęka',
  'Bielany',
  'Mokotów',
  'Ochota',
  'Praga-Południe',
  'Praga-Północ',
  'Rembertów',
  'Śródmieście',
  'Targówek',
  'Ursus',
  'Ursynów',
  'Wawer',
  'Wesoła',
  'Wilanów',
  'Włochy',
  'Wola',
  'Żoliborz',
] as const;

// ------------------------------------------------------------------- levels

export type PaceLevel = 'slow' | 'normal' | 'fast';
export type BikeLevel = 'beginner' | 'recreational' | 'fit' | 'sport';
export type WheelchairType = 'none' | 'manual' | 'electric';

export interface LevelDef<L extends string> {
  id: L;
  label: string;
  /** Average speed of the level, km/h. */
  kmh: number;
}

export const WALK_LEVELS: LevelDef<PaceLevel>[] = [
  { id: 'slow', label: 'Spokojnie', kmh: 3.4 },
  { id: 'normal', label: 'Normalnie', kmh: 4.8 },
  { id: 'fast', label: 'Szybko', kmh: 6 },
];

export const BIKE_LEVELS: LevelDef<BikeLevel>[] = [
  { id: 'beginner', label: 'Początkujący', kmh: 9 },
  { id: 'recreational', label: 'Rekreacyjny', kmh: 13 },
  { id: 'fit', label: 'Sprawny', kmh: 18 },
  { id: 'sport', label: 'Sportowy', kmh: 24 },
];

export const WHEELCHAIR_LEVELS: Record<'manual' | 'electric', LevelDef<PaceLevel>[]> = {
  manual: [
    { id: 'slow', label: 'Spokojnie', kmh: 2.5 },
    { id: 'normal', label: 'Normalnie', kmh: 3.6 },
    { id: 'fast', label: 'Szybko', kmh: 5 },
  ],
  electric: [
    { id: 'slow', label: 'Spokojnie', kmh: 3 },
    { id: 'normal', label: 'Normalnie', kmh: 5 },
    { id: 'fast', label: 'Szybko', kmh: 6 },
  ],
};

export const WHEELCHAIR_LABEL: Record<WheelchairType, string> = {
  none: 'Brak',
  manual: 'Ręczny',
  electric: 'Elektryczny',
};

/** Allowed range of an average speed typed by the user, km/h. */
export const SPEED_RANGE = {
  walking: [1, 10],
  cycling: [3, 45],
  wheelchair: [1, 15],
} as const;

// -------------------------------------------------------------- preferences

export interface WalkingSetting {
  level: PaceLevel;
  /** Average speed typed by the user (replaces the level). */
  customKmh: number | null;
  /** Always use the average speed from the trip history (once there are enough trips). */
  autoSpeed: boolean;
}

export interface CyclingSetting {
  /** False = the user does not ride Veturilo bikes. */
  enabled: boolean;
  level: BikeLevel;
  customKmh: number | null;
  autoSpeed: boolean;
}

export interface WheelchairSetting {
  type: WheelchairType;
  level: PaceLevel;
  customKmh: number | null;
  autoSpeed: boolean;
  stepFree: boolean;
  lowFloorOnly: boolean;
  preferLifts: boolean;
}

export interface AreaPoint {
  id: string;
  label: string;
  position: LatLng;
  radiusM: number;
}

export interface ExcludedAreas {
  districts: string[];
  points: AreaPoint[];
}

export interface Preferences {
  walking: WalkingSetting;
  cycling: CyclingSetting;
  wheelchair: WheelchairSetting;
  priorities: {
    /** null = any number of transfers. */
    maxTransfers: number | null;
    excluded: ExcludedAreas;
  };
}

export const DEFAULT_PREFERENCES: Preferences = {
  walking: { level: 'normal', customKmh: null, autoSpeed: false },
  cycling: { enabled: true, level: 'recreational', customKmh: null, autoSpeed: false },
  wheelchair: {
    type: 'none',
    level: 'normal',
    customKmh: null,
    autoSpeed: false,
    stepFree: false,
    lowFloorOnly: false,
    preferLifts: false,
  },
  priorities: { maxTransfers: null, excluded: { districts: [], points: [] } },
};

export const walkingKmh = (s: WalkingSetting) =>
  s.customKmh ?? WALK_LEVELS.find((l) => l.id === s.level)!.kmh;

export const cyclingKmh = (s: CyclingSetting) =>
  s.customKmh ?? BIKE_LEVELS.find((l) => l.id === s.level)!.kmh;

export function wheelchairKmh(s: WheelchairSetting): number | null {
  if (s.type === 'none') return null;
  return s.customKmh ?? WHEELCHAIR_LEVELS[s.type].find((l) => l.id === s.level)!.kmh;
}

export const formatKmh = (kmh: number) => `${String(kmh).replace('.', ',')} km/h`;

/** Short one-line summary pieces, e.g. for the top of the route list. */
export function summarize(p: Preferences): string[] {
  const out: string[] = [];
  out.push(`Pieszo ${formatKmh(walkingKmh(p.walking))}`);
  out.push(p.cycling.enabled ? `Rower ${formatKmh(cyclingKmh(p.cycling))}` : 'Bez roweru');
  const w = wheelchairKmh(p.wheelchair);
  if (w !== null) out.push(`Wózek ${formatKmh(w)}`);
  if (p.wheelchair.stepFree) out.push('Bez schodów');
  if (p.priorities.maxTransfers !== null) out.push(`Maks. przesiadek: ${p.priorities.maxTransfers}`);
  const areas = p.priorities.excluded.districts.length + p.priorities.excluded.points.length;
  if (areas > 0) out.push(`Omijam: ${areas}`);
  return out;
}

// --------------------------------------------------------------- time rules

/** Replacements of whole preference sections. A missing key = not overridden. */
export interface PreferenceOverrides {
  walking?: WalkingSetting;
  cycling?: CyclingSetting;
  wheelchair?: WheelchairSetting;
  /** `null` is a real value: any number of transfers. */
  maxTransfers?: number | null;
  excluded?: ExcludedAreas;
}

export interface TimeRule {
  id: string;
  name: string;
  /** 0 = Monday ... 6 = Sunday. */
  days: number[];
  /** "HH:mm"; `to` earlier than `from` means the rule runs past midnight. */
  from: string;
  to: string;
  overrides: PreferenceOverrides;
}

export const DAY_LABELS = ['Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'So', 'Nd'];

const toMinutes = (hhmm: string) => {
  const [h, m] = hhmm.split(':').map(Number);
  return h * 60 + m;
};

/** Minutes since the rule started if it is active at `now`, else null. */
export function ruleElapsed(rule: TimeRule, now: Date): number | null {
  const day = (now.getDay() + 6) % 7;
  const cur = now.getHours() * 60 + now.getMinutes();
  const from = toMinutes(rule.from);
  const to = toMinutes(rule.to);

  if (from === to) return rule.days.includes(day) ? (cur - from + 1440) % 1440 : null; // all day
  if (from < to) return rule.days.includes(day) && cur >= from && cur < to ? cur - from : null;
  if (cur >= from) return rule.days.includes(day) ? cur - from : null;
  if (cur < to) return rule.days.includes((day + 6) % 7) ? cur + 1440 - from : null;
  return null;
}

export function applyOverrides(p: Preferences, o: PreferenceOverrides): Preferences {
  return {
    walking: o.walking ?? p.walking,
    cycling: o.cycling ?? p.cycling,
    wheelchair: o.wheelchair ?? p.wheelchair,
    priorities: {
      maxTransfers: o.maxTransfers !== undefined ? o.maxTransfers : p.priorities.maxTransfers,
      excluded: o.excluded ?? p.priorities.excluded,
    },
  };
}

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

/** The sections of `next` that differ from `base`, as overrides. */
export function diffOverrides(base: Preferences, next: Preferences): PreferenceOverrides {
  const o: PreferenceOverrides = {};
  if (!same(base.walking, next.walking)) o.walking = next.walking;
  if (!same(base.cycling, next.cycling)) o.cycling = next.cycling;
  if (!same(base.wheelchair, next.wheelchair)) o.wheelchair = next.wheelchair;
  if (base.priorities.maxTransfers !== next.priorities.maxTransfers) o.maxTransfers = next.priorities.maxTransfers;
  if (!same(base.priorities.excluded, next.priorities.excluded)) o.excluded = next.priorities.excluded;
  return o;
}

/** Preferences valid at `now`: the base ones with the active time rule (the most recently started) applied. */
export function effectivePreferences(
  base: Preferences,
  rules: TimeRule[],
  now: Date,
): { prefs: Preferences; activeRule: TimeRule | null } {
  let best: { rule: TimeRule; elapsed: number } | null = null;
  for (const rule of rules) {
    const elapsed = ruleElapsed(rule, now);
    if (elapsed !== null && (!best || elapsed < best.elapsed)) best = { rule, elapsed };
  }
  return best
    ? { prefs: applyOverrides(base, best.rule.overrides), activeRule: best.rule }
    : { prefs: base, activeRule: null };
}

/** The speed from the trip history that is used instead of the configured one, per mode. */
export type AutoSpeeds = Partial<Record<SpeedMode, { kmh: number; trips: number }>>;

/**
 * Where "always use the average from my history" is on and there are enough trips, the average
 * replaces the level / typed speed (as `customKmh`). Other modes are left as they are.
 */
export function applyHistory(p: Preferences, summary: SpeedSummary): { prefs: Preferences; used: AutoSpeeds } {
  const used: AutoSpeeds = {};
  const pick = (mode: SpeedMode, on: boolean) => {
    const s = summary[mode];
    if (on && s.enough && s.avgKmh !== null) {
      used[mode] = { kmh: s.avgKmh, trips: s.trips };
      return s.avgKmh;
    }
    return null;
  };
  const walking = pick('walking', p.walking.autoSpeed);
  const cycling = pick('cycling', p.cycling.enabled && p.cycling.autoSpeed);
  const wheelchair = pick('wheelchair', p.wheelchair.type !== 'none' && p.wheelchair.autoSpeed);
  return {
    used,
    prefs: {
      ...p,
      walking: walking === null ? p.walking : { ...p.walking, customKmh: walking },
      cycling: cycling === null ? p.cycling : { ...p.cycling, customKmh: cycling },
      wheelchair: wheelchair === null ? p.wheelchair : { ...p.wheelchair, customKmh: wheelchair },
    },
  };
}

export function describeRule(rule: TimeRule): string {
  const days =
    rule.days.length === 7 ? 'codziennie' : rule.days.length === 0 ? 'brak dni' : rule.days.map((d) => DAY_LABELS[d]).join(', ');
  return rule.from === rule.to ? `${days} · całą dobę` : `${days} · ${rule.from}–${rule.to}`;
}

// ------------------------------------------------------------ trip filters

export type SortKey = 'fastest' | 'fewest-transfers' | 'cheapest' | 'most-active';
export type FilterMode = Exclude<TransportMode, 'walk'>;

export const SORT_LABELS: Record<SortKey, string> = {
  fastest: 'Najszybsze',
  'fewest-transfers': 'Najmniej przesiadek',
  cheapest: 'Najtańsze',
  'most-active': 'Najaktywniejsze',
};

export const FILTER_MODES: FilterMode[] = ['bus', 'tram', 'metro', 'rail', 'bike'];

export interface TripFilters {
  sort: SortKey;
  /** Allowed vehicles; null = all. */
  modes: FilterMode[] | null;
  /** Max total walking time in minutes; null = no limit. */
  maxWalkMin: number | null;
  /** Changes of the preferences for this search only. */
  overrides: PreferenceOverrides;
}

export const DEFAULT_FILTERS: TripFilters = { sort: 'fastest', modes: null, maxWalkMin: null, overrides: {} };

export interface FilterChip {
  id: 'sort' | 'modes' | 'walk' | 'maxTransfers' | 'walking' | 'cycling' | 'wheelchair' | 'excluded';
  label: string;
}

const MODE_NAMES: Record<FilterMode, string> = {
  bus: 'Autobus',
  tram: 'Tramwaj',
  metro: 'Metro',
  rail: 'Kolej',
  bike: 'Veturilo',
};
export const modeName = (m: FilterMode) => MODE_NAMES[m];

/** Chips for the filters that differ from the defaults. `trip` = preferences with the overrides applied. */
export function filterChips(f: TripFilters, trip: Preferences): FilterChip[] {
  const chips: FilterChip[] = [];
  if (f.sort !== DEFAULT_FILTERS.sort) chips.push({ id: 'sort', label: SORT_LABELS[f.sort] });
  if (f.modes) chips.push({ id: 'modes', label: f.modes.length ? f.modes.map(modeName).join(', ') : 'Bez pojazdów' });
  if (f.maxWalkMin !== null) chips.push({ id: 'walk', label: `Pieszo do ${f.maxWalkMin} min` });
  const o = f.overrides;
  if (o.maxTransfers !== undefined)
    chips.push({
      id: 'maxTransfers',
      label: trip.priorities.maxTransfers === null ? 'Dowolna liczba przesiadek' : `Maks. przesiadek: ${trip.priorities.maxTransfers}`,
    });
  if (o.walking) chips.push({ id: 'walking', label: `Pieszo ${formatKmh(walkingKmh(trip.walking))}` });
  if (o.cycling)
    chips.push({ id: 'cycling', label: trip.cycling.enabled ? `Rower ${formatKmh(cyclingKmh(trip.cycling))}` : 'Bez roweru' });
  if (o.wheelchair) {
    const w = wheelchairKmh(trip.wheelchair);
    chips.push({ id: 'wheelchair', label: w === null ? 'Bez wózka' : `Wózek ${formatKmh(w)}` });
  }
  if (o.excluded) {
    const n = trip.priorities.excluded.districts.length + trip.priorities.excluded.points.length;
    chips.push({ id: 'excluded', label: n ? `Omijam: ${n}` : 'Bez wykluczeń' });
  }
  return chips;
}

export function clearFilter(f: TripFilters, id: FilterChip['id']): TripFilters {
  const { overrides } = f;
  switch (id) {
    case 'sort':
      return { ...f, sort: DEFAULT_FILTERS.sort };
    case 'modes':
      return { ...f, modes: null };
    case 'walk':
      return { ...f, maxWalkMin: null };
    case 'maxTransfers': {
      const { maxTransfers: _drop, ...rest } = overrides;
      return { ...f, overrides: rest };
    }
    default: {
      const rest = { ...overrides };
      delete rest[id as 'walking' | 'cycling' | 'wheelchair' | 'excluded'];
      return { ...f, overrides: rest };
    }
  }
}

export const countActiveFilters = (f: TripFilters, trip: Preferences) => filterChips(f, trip).length;

const walkMinutes = (o: RouteOption) => o.legs.filter((l) => l.mode === 'walk').reduce((s, l) => s + l.durationMin, 0);

/**
 * Client-side filtering and sorting of the routes that were found. Only list-like filters work here
 * (transfers, vehicles, walking time, sorting); speeds, wheelchair and areas need the routing backend.
 */
export function applyListFilters(options: RouteOption[], trip: Preferences, f: TripFilters): RouteOption[] {
  const maxTransfers = trip.priorities.maxTransfers;
  const list = options.filter((o) => {
    if (maxTransfers !== null && o.transfers > maxTransfers) return false;
    if (f.modes && o.legs.some((l) => l.mode !== 'walk' && !f.modes!.includes(l.mode as FilterMode))) return false;
    if (f.maxWalkMin !== null && walkMinutes(o) > f.maxWalkMin) return false;
    return true;
  });

  const by: Record<SortKey, (a: RouteOption, b: RouteOption) => number> = {
    fastest: (a, b) => a.durationMin - b.durationMin,
    'fewest-transfers': (a, b) => a.transfers - b.transfers || a.durationMin - b.durationMin,
    cheapest: (a, b) => a.costPln - b.costPln || a.durationMin - b.durationMin,
    'most-active': (a, b) => b.calories - a.calories || a.durationMin - b.durationMin,
  };
  return [...list].sort(by[f.sort]);
}

// ------------------------------------------------------------------ storage

export interface StoredPreferences {
  version: 1;
  base: Preferences;
  rules: TimeRule[];
}

/** Fills in anything missing in stored data (older versions, hand-edited storage). */
export function sanitizeStored(raw: unknown): StoredPreferences {
  const r = (raw ?? {}) as Partial<StoredPreferences>;
  const b = (r.base ?? {}) as Partial<Preferences>;
  const d = DEFAULT_PREFERENCES;
  return {
    version: 1,
    base: {
      walking: { ...d.walking, ...b.walking },
      cycling: { ...d.cycling, ...b.cycling },
      wheelchair: { ...d.wheelchair, ...b.wheelchair },
      priorities: {
        maxTransfers: b.priorities?.maxTransfers ?? d.priorities.maxTransfers,
        excluded: { ...d.priorities.excluded, ...b.priorities?.excluded },
      },
    },
    rules: Array.isArray(r.rules) ? r.rules : [],
  };
}
