import {
  Modality, MovementPattern, SectionFormat, SectionKind, SetIn, Training,
} from './models';

export const MODALITIES: { value: Modality; label: string }[] = [
  { value: 'G', label: 'Гімнастика' },
  { value: 'W', label: 'Силові' },
  { value: 'M', label: 'Кардіо' },
];
export const MODALITY_LABEL: Record<Modality, string> = {
  G: 'Гімнастика', W: 'Силові', M: 'Кардіо',
};

export const PATTERNS: { value: MovementPattern; label: string }[] = [
  { value: 'squat', label: 'Присідання' },
  { value: 'hinge', label: 'Нахил / тяга (hinge)' },
  { value: 'push', label: 'Жим' },
  { value: 'pull', label: 'Тяга' },
  { value: 'carry', label: 'Перенесення' },
  { value: 'core', label: 'Кор' },
  { value: 'locomotion', label: 'Пересування' },
  { value: 'other', label: 'Інше' },
];
export const PATTERN_LABEL = Object.fromEntries(
  PATTERNS.map((p) => [p.value, p.label]),
) as Record<MovementPattern, string>;

export const KINDS: { value: SectionKind; label: string }[] = [
  { value: 'warm_up', label: 'Розминка' },
  { value: 'lifting', label: 'Силова частина' },
  { value: 'metcon', label: 'Metcon' },
  { value: 'accessory', label: 'Допоміжна' },
  { value: 'cool_down', label: 'Заминка' },
];
export const KIND_LABEL = Object.fromEntries(
  KINDS.map((k) => [k.value, k.label]),
) as Record<SectionKind, string>;

export const FORMATS: { value: SectionFormat; label: string }[] = [
  { value: 'standard', label: 'Стандарт' },
  { value: 'amrap', label: 'AMRAP' },
  { value: 'emom', label: 'EMOM' },
  { value: 'for_time', label: 'For Time' },
  { value: 'tabata', label: 'Табата' },
];
export const FORMAT_LABEL = Object.fromEntries(
  FORMATS.map((f) => [f.value, f.label]),
) as Record<SectionFormat, string>;

export function humanize(value: string): string {
  return value.replace(/_/g, ' ');
}

export function formatDuration(sec: number): string {
  if (sec < 60) return `${sec} с`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return s ? `${m} хв ${s} с` : `${m} хв`;
}

/** "5 × 100 кг · RPE 8", "12 повт.", "500 м · 2 хв", ... */
export function formatSet(s: SetIn): string {
  const parts: string[] = [];
  switch (s.type) {
    case 'G':
      parts.push(`${s.reps} повт.`);
      if (s.weight) parts.push(`${s.weight} кг`);
      if (s.time) parts.push(formatDuration(s.time));
      break;
    case 'W':
      parts.push(s.weight ? `${s.reps} × ${s.weight} кг` : `${s.reps} повт.`);
      if (s.rpe) parts.push(`RPE ${s.rpe}`);
      if (s.time) parts.push(formatDuration(s.time));
      break;
    case 'M':
      if (s.time) parts.push(formatDuration(s.time));
      if (s.calories) parts.push(`${s.calories} ккал`);
      if (s.distance) parts.push(`${s.distance} м`);
      break;
  }
  return parts.join(' · ');
}

/** Ukrainian plural: plural(5, ['підхід', 'підходи', 'підходів']) */
export function plural(n: number, forms: [string, string, string]): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return forms[1];
  return forms[2];
}

// ---------------------------------------------------------------- dates

const pad = (n: number) => String(n).padStart(2, '0');

/** Local date as YYYY-MM-DD (not UTC, so the day never shifts). */
export function toIsoDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function parseIsoDate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d);
}

export function formatDateLong(iso: string): string {
  return parseIsoDate(iso).toLocaleDateString('uk-UA', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });
}

export function formatDateShort(iso: string): string {
  return parseIsoDate(iso).toLocaleDateString('uk-UA', {
    day: 'numeric', month: 'short', year: 'numeric',
  });
}

// ------------------------------------------------------------ summaries

export interface TrainingSummary {
  sections: number;
  sets: number;
  kinds: SectionKind[];
  exercises: string;
}

const summaryCache = new WeakMap<Training, TrainingSummary>();

export function summarize(t: Training): TrainingSummary {
  const cached = summaryCache.get(t);
  if (cached) return cached;
  const kinds: SectionKind[] = [];
  const names: string[] = [];
  let sets = 0;
  for (const s of t.sections) {
    if (!kinds.includes(s.kind)) kinds.push(s.kind);
    for (const it of s.items) {
      sets++;
      if (!names.includes(it.exercise.name)) names.push(it.exercise.name);
    }
  }
  const rest = names.length - 3;
  const shown = names.slice(0, 3).join(', ');
  const result = {
    sections: t.sections.length,
    sets,
    kinds,
    exercises: rest > 0 ? `${shown} +${rest}` : shown,
  };
  summaryCache.set(t, result);
  return result;
}

/** Sum of reps * weight over all sets that have both, in kilograms (derived, not stored). */
export function tonnage(t: Training): number {
  let sum = 0;
  for (const s of t.sections) {
    for (const it of s.items) {
      if (it.type !== 'M' && it.reps && it.weight) sum += it.reps * it.weight;
    }
  }
  return Math.round(sum);
}
