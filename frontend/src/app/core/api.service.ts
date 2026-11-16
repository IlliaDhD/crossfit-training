import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { API_URL } from './api.config';
import {
  AthleteProfile, AthleteProfilePatch, BodyMeasurement, DistanceBest, Exercise, ExerciseIn, Page,
  RelativeStrengthPoint, StrengthRecord, TonnageGroup, TonnagePoint, Training, TrainingIn,
} from './models';

/** Builds HttpParams and skips undefined / null / empty values. */
function params(q: Record<string, string | number | null | undefined>): HttpParams {
  const fromObject: Record<string, string | number> = {};
  for (const [key, value] of Object.entries(q)) {
    if (value !== undefined && value !== null && value !== '') fromObject[key] = value;
  }
  return new HttpParams({ fromObject });
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);

  listExercises(limit: number, offset: number): Observable<Page<Exercise>> {
    return this.http.get<Page<Exercise>>(`${API_URL}/exercises`, {
      params: new HttpParams({ fromObject: { limit, offset } }),
    });
  }

  /** Coach only (the backend returns 403 for other roles). */
  createExercise(body: ExerciseIn): Observable<Exercise> {
    return this.http.post<Exercise>(`${API_URL}/exercises`, body);
  }

  listTrainings(q: {
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Observable<Page<Training>> {
    const fromObject: Record<string, string | number> = {};
    for (const [key, value] of Object.entries(q)) {
      if (value !== undefined) fromObject[key] = value;
    }
    return this.http.get<Page<Training>>(`${API_URL}/trainings`, {
      params: new HttpParams({ fromObject }),
    });
  }

  getTraining(id: string): Observable<Training> {
    return this.http.get<Training>(`${API_URL}/trainings/${id}`);
  }

  createTraining(body: TrainingIn): Observable<Training> {
    return this.http.post<Training>(`${API_URL}/trainings`, body);
  }

  deleteTraining(id: string): Observable<void> {
    return this.http.delete<void>(`${API_URL}/trainings/${id}`);
  }

  // ---- athlete profile and body weight

  getProfile(): Observable<AthleteProfile> {
    return this.http.get<AthleteProfile>(`${API_URL}/me/profile`);
  }

  patchProfile(body: AthleteProfilePatch): Observable<AthleteProfile> {
    return this.http.patch<AthleteProfile>(`${API_URL}/me/profile`, body);
  }

  listMeasurements(q: { date_from?: string; date_to?: string; limit?: number; offset?: number } = {}) {
    return this.http.get<Page<BodyMeasurement>>(`${API_URL}/me/body-measurements`, { params: params(q) });
  }

  /** One value per day: calling it again for the same date edits the value. */
  putMeasurement(date: string, weightKg: number): Observable<BodyMeasurement> {
    return this.http.put<BodyMeasurement>(`${API_URL}/me/body-measurements/${date}`, { weight_kg: weightKg });
  }

  deleteMeasurement(date: string): Observable<void> {
    return this.http.delete<void>(`${API_URL}/me/body-measurements/${date}`);
  }

  // ---- statistics

  tonnage(q: { group_by: TonnageGroup; date_from?: string; date_to?: string }): Observable<TonnagePoint[]> {
    return this.http.get<TonnagePoint[]>(`${API_URL}/stats/tonnage`, { params: params(q) });
  }

  relativeStrength(q: {
    exercise_id: string; reps: number; date_from?: string; date_to?: string;
  }): Observable<RelativeStrengthPoint[]> {
    return this.http.get<RelativeStrengthPoint[]>(`${API_URL}/stats/relative-strength`, { params: params(q) });
  }

  strengthRecords(q: {
    exercise_id?: string; reps?: number | null; date_from?: string; date_to?: string;
  }): Observable<StrengthRecord[]> {
    return this.http.get<StrengthRecord[]>(`${API_URL}/stats/strength-records`, { params: params(q) });
  }

  distanceBests(q: { exercise_id?: string } = {}): Observable<DistanceBest[]> {
    return this.http.get<DistanceBest[]>(`${API_URL}/stats/distance-bests`, { params: params(q) });
  }
}
