import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { API_URL } from './api.config';
import { Exercise, ExerciseIn, Page, Training, TrainingIn } from './models';

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
}
