import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from './api.service';
import { errorMessage } from './errors';
import { Exercise } from './models';

const PAGE = 100; // maximum allowed by the API

/** The exercise catalog is small (a few hundred items): load it once and filter on the client. */
@Injectable({ providedIn: 'root' })
export class CatalogService {
  private api = inject(ApiService);

  readonly exercises = signal<Exercise[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  /** Adds a freshly created exercise so it shows up in the catalog without a reload. */
  add(exercise: Exercise) {
    this.exercises.update((list) =>
      [...list, exercise].sort((a, b) => a.name.localeCompare(b.name)),
    );
  }

  async load(force = false): Promise<void> {
    if (this.loading() || (this.exercises().length > 0 && !force)) return;
    this.loading.set(true);
    this.error.set(null);
    try {
      const all: Exercise[] = [];
      let total = 0;
      do {
        const page = await firstValueFrom(this.api.listExercises(PAGE, all.length));
        all.push(...page.items);
        total = page.total;
        if (page.items.length === 0) break;
      } while (all.length < total);
      all.sort((a, b) => a.name.localeCompare(b.name));
      this.exercises.set(all.filter((e) => !e.is_archived));
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.loading.set(false);
    }
  }
}
