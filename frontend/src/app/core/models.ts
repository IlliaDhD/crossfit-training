// Mirrors the backend schemas (backend/src/crosfit_training_backend/api/schemas).
// Units: time - seconds, distance - meters, weight - kilograms.

export type Modality = 'G' | 'W' | 'M'; // G - gymnastics, W - weight, M - cardio
export type MovementPattern =
  | 'squat' | 'hinge' | 'push' | 'pull' | 'carry' | 'core' | 'locomotion' | 'other';
export type SectionKind = 'warm_up' | 'lifting' | 'metcon' | 'accessory' | 'cool_down';
export type SectionFormat = 'standard' | 'amrap' | 'emom' | 'for_time' | 'tabata';

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Exercise {
  id: string;
  slug: string;
  name: string;
  search_terms: string[];
  modality: Modality;
  movement_pattern: MovementPattern | null;
  muscle_groups: string[];
  equipment: string[];
  is_archived: boolean;
}

export interface ExerciseIn {
  slug: string; // ^[a-z0-9-]+$
  name: string;
  modality: Modality;
  movement_pattern?: MovementPattern | null;
  muscle_groups: string[];
  equipment: string[];
}

// ---- sets sent to the API
export interface GymSetIn {
  type: 'G';
  exercise_id: string;
  reps: number;
  time?: number | null;
  weight?: number | null;
  comment?: string | null;
}
export interface WeightSetIn {
  type: 'W';
  exercise_id: string;
  reps: number;
  weight?: number | null;
  rpe?: number | null;
  time?: number | null;
  comment?: string | null;
}
export interface CardioSetIn {
  type: 'M';
  exercise_id: string;
  time?: number | null;
  calories?: number | null;
  distance?: number | null;
  comment?: string | null;
}
export type SetIn = GymSetIn | WeightSetIn | CardioSetIn;

// ---- sets returned by the API (with an exercise snapshot)
export interface ExerciseSnapshot {
  name: string;
  movement_pattern?: string | null;
  muscle_groups: string[];
  equipment: string[];
}
export interface ComplexMarker {
  id: string;
  name: string;
  round: number;
}
export type SetOut = SetIn & { exercise: ExerciseSnapshot; complex?: ComplexMarker | null };

export interface SectionIn {
  kind: SectionKind;
  format: SectionFormat;
  rounds?: number;
  time_cap?: number;
  items: SetIn[];
  comment?: string;
}
export interface Section {
  kind: SectionKind;
  format: SectionFormat;
  rounds: number | null;
  time_cap: number | null;
  items: SetOut[];
  comment: string | null;
}

export interface TrainingIn {
  title: string;
  date: string; // YYYY-MM-DD
  comment?: string;
  sections: SectionIn[];
}
export interface Training {
  id: string;
  title: string;
  date: string;
  comment: string | null;
  sections: Section[];
  created_at: string;
  updated_at: string;
}
