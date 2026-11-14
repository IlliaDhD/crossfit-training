import { Component, OnInit, inject } from '@angular/core';
import Keycloak from 'keycloak-js';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ADMIN_ROLE } from '../core/api.config';
import { ApiService } from '../core/api.service';
import { CatalogService } from '../core/catalog.service';
import { errorMessage } from '../core/errors';
import { FORMATS, KINDS, toIsoDate } from '../core/format';
import {
  Exercise, SectionFormat, SectionIn, SectionKind, SetIn, TrainingIn,
} from '../core/models';
import { NewExerciseDialogComponent } from './new-exercise-dialog.component';

let nextUid = 1;

interface DraftSet {
  uid: number;
  exercise: Exercise;
  reps: number | null;
  weight: number | null;
  time: number | null;
  rpe: number | null;
  calories: number | null;
  distance: number | null;
  comment: string;
}

interface DraftSection {
  uid: number;
  kind: SectionKind;
  format: SectionFormat;
  rounds: number | null;
  timeCapMin: number | null;
  comment: string;
  items: DraftSet[];
  query: string;
  results: Exercise[];
}

@Component({
  selector: 'app-builder',
  standalone: true,
  imports: [FormsModule, NewExerciseDialogComponent],
  template: `
    <header class="head">
      <h2>Конструктор тренувань</h2>
      <p class="x-muted">Зберіть тренування із секцій і вправ та збережіть його в журнал.</p>
    </header>

    <div class="x-card meta">
      <label class="field grow">
        <span>Назва</span>
        <input class="x-input" maxlength="120" placeholder="Напр. Heavy Day" [(ngModel)]="title" />
      </label>
      <label class="field">
        <span>Дата</span>
        <input class="x-input" type="date" [(ngModel)]="date" />
      </label>
      <label class="field full">
        <span>Коментар</span>
        <textarea class="x-input" rows="2" [(ngModel)]="comment"></textarea>
      </label>
    </div>

    @if (catalog.error(); as err) {
      <div class="x-error">{{ err }}</div>
    }

    @for (s of sections; track s.uid; let i = $index) {
      <article class="x-card section">
        <div class="sec-head">
          <span class="num">{{ i + 1 }}</span>
          <label class="field">
            <span>Тип</span>
            <select class="x-input" [(ngModel)]="s.kind">
              @for (k of kinds; track k.value) {
                <option [value]="k.value">{{ k.label }}</option>
              }
            </select>
          </label>
          <label class="field">
            <span>Формат</span>
            <select class="x-input" [(ngModel)]="s.format">
              @for (f of formats; track f.value) {
                <option [value]="f.value">{{ f.label }}</option>
              }
            </select>
          </label>
          <label class="field narrow">
            <span>Раунди</span>
            <input class="x-input" type="number" min="1" [(ngModel)]="s.rounds" />
          </label>
          <label class="field narrow">
            <span>Time cap, хв</span>
            <input class="x-input" type="number" min="1" [(ngModel)]="s.timeCapMin" />
          </label>
          <div class="sec-actions">
            <button type="button" class="x-btn small ghost" aria-label="Секцію вгору" [disabled]="i === 0" (click)="moveSection(i, -1)">↑</button>
            <button type="button" class="x-btn small ghost" aria-label="Секцію вниз" [disabled]="i === sections.length - 1" (click)="moveSection(i, 1)">↓</button>
            <button type="button" class="x-btn small danger" aria-label="Видалити секцію" (click)="removeSection(i)">✕</button>
          </div>
        </div>

        @if (s.format === 'amrap' || s.format === 'emom') {
          <p class="hint">Для {{ s.format.toUpperCase() }} потрібен time cap.</p>
        } @else if (s.format === 'for_time') {
          <p class="hint">Для For Time потрібна кількість раундів.</p>
        }

        @for (it of s.items; track it.uid; let j = $index) {
          <div class="set">
            <div class="set-name">
              <span class="x-badge" [attr.data-m]="it.exercise.modality">{{ it.exercise.modality }}</span>
              <span class="nm">{{ it.exercise.name }}</span>
            </div>
            <div class="nums">
              @if (it.exercise.modality !== 'M') {
                <label class="mini"><span>Повтори</span><input class="x-input" type="number" min="1" [(ngModel)]="it.reps" /></label>
                <label class="mini"><span>Вага, кг</span><input class="x-input" type="number" min="0" step="0.5" [(ngModel)]="it.weight" /></label>
              }
              @if (it.exercise.modality === 'W') {
                <label class="mini"><span>RPE (1-10)</span><input class="x-input" type="number" min="1" max="10" step="0.5" [(ngModel)]="it.rpe" /></label>
              }
              <label class="mini"><span>Час, с</span><input class="x-input" type="number" min="1" [(ngModel)]="it.time" /></label>
              @if (it.exercise.modality === 'M') {
                <label class="mini"><span>Ккал</span><input class="x-input" type="number" min="1" [(ngModel)]="it.calories" /></label>
                <label class="mini"><span>Дистанція, м</span><input class="x-input" type="number" min="1" [(ngModel)]="it.distance" /></label>
              }
              <label class="mini grow"><span>Коментар</span><input class="x-input" [(ngModel)]="it.comment" /></label>
            </div>
            <div class="set-actions">
              <button type="button" class="x-btn small ghost" title="Дублювати підхід" aria-label="Дублювати підхід" (click)="duplicateSet(s, j)">⧉</button>
              <button type="button" class="x-btn small danger" aria-label="Видалити підхід" (click)="removeSet(s, j)">✕</button>
            </div>
          </div>
        }

        <div class="picker">
          <input
            class="x-input"
            type="search"
            placeholder="+ Додати вправу: почніть вводити назву…"
            aria-label="Додати вправу"
            [ngModel]="s.query"
            (ngModelChange)="onQuery(s, $event)"
            (keydown.enter)="addFirst(s)"
          />
          @if (s.results.length) {
            <ul class="results">
              @for (ex of s.results; track ex.id) {
                <li>
                  <button type="button" (click)="addSet(s, ex)">
                    <span class="x-badge" [attr.data-m]="ex.modality">{{ ex.modality }}</span>
                    {{ ex.name }}
                  </button>
                </li>
              }
            </ul>
          } @else if (s.query.trim() && !catalog.loading()) {
            <p class="x-muted none">Нічого не знайдено</p>
          }
          @if (canCreateExercise) {
            <button type="button" class="x-btn small ghost new-ex" (click)="creatingFor = s">
              + Створити нову вправу{{ s.query.trim() ? ' «' + s.query.trim() + '»' : '' }}
            </button>
          }
        </div>

        <label class="field full">
          <span>Коментар до секції</span>
          <input class="x-input" [(ngModel)]="s.comment" />
        </label>
      </article>
    }

    <div class="bottom">
      <button type="button" class="x-btn" (click)="addSection()">+ Додати секцію</button>
    </div>

    @if (errors.length) {
      <div class="x-error">
        <strong>Виправте перед збереженням:</strong>
        <ul>
          @for (e of errors; track e) {
            <li>{{ e }}</li>
          }
        </ul>
      </div>
    }
    @if (serverError) {
      <div class="x-error">{{ serverError }}</div>
    }

    @if (creatingFor; as target) {
      <app-new-exercise-dialog
        [initialName]="target.query"
        (created)="onExerciseCreated($event)"
        (dismissed)="creatingFor = null"
      />
    }

    <div class="footer">
      <button type="button" class="x-btn ghost" [disabled]="saving" (click)="reset()">Очистити</button>
      <button type="button" class="x-btn primary" [disabled]="saving" (click)="save()">
        {{ saving ? 'Збереження…' : 'Зберегти тренування' }}
      </button>
    </div>
  `,
  styles: [
    `
      .head h2 { margin: 0 0 0.2rem; }
      .head p { margin: 0 0 1rem; }
      .meta, .section { display: flex; flex-wrap: wrap; gap: 0.8rem; margin-bottom: 1rem; }
      .field { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.8rem; color: var(--x-muted); min-width: 140px; }
      .field.grow { flex: 1 1 260px; }
      .field.full { flex: 1 1 100%; }
      .field.narrow { min-width: 100px; width: 110px; }
      .section { flex-direction: column; }
      .sec-head { display: flex; flex-wrap: wrap; gap: 0.7rem; align-items: flex-end; }
      .num {
        width: 2rem; height: 2rem; display: grid; place-items: center; border-radius: 50%;
        background: var(--x-accent); font-weight: 800; align-self: center;
      }
      .sec-actions { margin-left: auto; display: flex; gap: 0.3rem; }
      .hint { margin: 0; font-size: 0.85rem; color: var(--x-warn); }
      .set {
        display: flex; flex-wrap: wrap; gap: 0.7rem; align-items: flex-end; padding: 0.7rem;
        border-radius: 12px; background: var(--x-overlay); border: 1px solid var(--x-border);
      }
      .set-name { display: flex; gap: 0.5rem; align-items: center; min-width: 190px; align-self: center; }
      .nm { font-weight: 700; }
      .nums { display: flex; flex-wrap: wrap; gap: 0.6rem; flex: 1; }
      .mini { display: flex; flex-direction: column; gap: 0.2rem; font-size: 0.72rem; color: var(--x-muted); width: 100px; }
      .mini.grow { flex: 1 1 160px; width: auto; }
      .set-actions { display: flex; gap: 0.3rem; }
      .picker { position: relative; }
      .results {
        list-style: none; margin: 0.3rem 0 0; padding: 0.3rem; border-radius: 12px;
        background: var(--x-surface-2); border: 1px solid var(--x-border);
      }
      .results button {
        width: 100%; display: flex; gap: 0.6rem; align-items: center; text-align: left; cursor: pointer;
        padding: 0.45rem 0.6rem; border: none; border-radius: 8px; background: transparent;
        color: var(--x-text); font: inherit;
      }
      .results button:hover, .results button:focus-visible { background: var(--x-overlay-2); }
      .none { margin: 0.4rem 0 0; font-size: 0.85rem; }
      .new-ex { margin-top: 0.4rem; }
      .bottom { margin-bottom: 1rem; }
      .footer { display: flex; justify-content: flex-end; gap: 0.7rem; margin: 1rem 0 2rem; }
      .x-error { margin-bottom: 1rem; }
      .x-error ul { margin: 0.3rem 0 0; padding-left: 1.2rem; }
    `,
  ],
})
export class BuilderComponent implements OnInit {
  readonly catalog = inject(CatalogService);
  private api = inject(ApiService);
  private router = inject(Router);
  private keycloak = inject(Keycloak);

  readonly kinds = KINDS;
  readonly formats = FORMATS;

  title = '';
  date = toIsoDate(new Date());
  comment = '';
  sections: DraftSection[] = [this.newSection()];

  /** Only the coach may create exercises; the backend enforces it too (403). */
  readonly canCreateExercise: boolean = (
    (this.keycloak.tokenParsed?.['realm_access']?.roles as string[] | undefined) ?? []
  ).includes(ADMIN_ROLE);
  creatingFor: DraftSection | null = null;

  errors: string[] = [];
  serverError = '';
  saving = false;

  ngOnInit() {
    this.catalog.load();
  }

  // ------------------------------------------------------------ sections

  private newSection(): DraftSection {
    return {
      uid: nextUid++,
      kind: 'lifting',
      format: 'standard',
      rounds: null,
      timeCapMin: null,
      comment: '',
      items: [],
      query: '',
      results: [],
    };
  }

  addSection() {
    this.sections.push(this.newSection());
  }

  removeSection(i: number) {
    this.sections.splice(i, 1);
  }

  moveSection(i: number, dir: -1 | 1) {
    const j = i + dir;
    if (j < 0 || j >= this.sections.length) return;
    [this.sections[i], this.sections[j]] = [this.sections[j], this.sections[i]];
  }

  reset() {
    this.title = '';
    this.comment = '';
    this.date = toIsoDate(new Date());
    this.sections = [this.newSection()];
    this.errors = [];
    this.serverError = '';
  }

  // ---------------------------------------------------------------- sets

  onQuery(s: DraftSection, value: string) {
    s.query = value;
    const q = value.trim().toLowerCase();
    if (!q) {
      s.results = [];
      return;
    }
    s.results = this.catalog
      .exercises()
      .filter((e) => e.name.toLowerCase().includes(q) || e.search_terms.some((t) => t.includes(q)))
      .sort((a, b) => Number(b.name.toLowerCase().startsWith(q)) - Number(a.name.toLowerCase().startsWith(q)))
      .slice(0, 8);
  }

  addFirst(s: DraftSection) {
    if (s.results.length) this.addSet(s, s.results[0]);
  }

  addSet(s: DraftSection, exercise: Exercise) {
    s.items.push({
      uid: nextUid++,
      exercise,
      reps: exercise.modality === 'G' ? 10 : exercise.modality === 'W' ? 5 : null,
      weight: null,
      time: null,
      rpe: null,
      calories: null,
      distance: null,
      comment: '',
    });
    s.query = '';
    s.results = [];
  }

  /** A new exercise goes into the shared catalog and straight into the section it was created for. */
  onExerciseCreated(exercise: Exercise) {
    this.catalog.add(exercise);
    if (this.creatingFor) this.addSet(this.creatingFor, exercise);
    this.creatingFor = null;
  }

  duplicateSet(s: DraftSection, j: number) {
    s.items.splice(j + 1, 0, { ...s.items[j], uid: nextUid++ });
  }

  removeSet(s: DraftSection, j: number) {
    s.items.splice(j, 1);
  }

  // ---------------------------------------------------------------- save

  async save() {
    this.serverError = '';
    this.errors = this.validate();
    if (this.errors.length) return;

    this.saving = true;
    try {
      const created = await firstValueFrom(this.api.createTraining(this.toPayload()));
      await this.router.navigate(['/trainings'], { queryParams: { id: created.id } });
    } catch (e) {
      this.serverError = errorMessage(e);
    } finally {
      this.saving = false;
    }
  }

  private validate(): string[] {
    const errs: string[] = [];
    if (!this.title.trim()) errs.push('Вкажіть назву тренування.');
    if (!this.date) errs.push('Вкажіть дату.');

    this.sections.forEach((s, i) => {
      const where = `Секція ${i + 1}`;
      if (s.items.length === 0) errs.push(`${where}: додайте хоча б одну вправу.`);
      if ((s.format === 'amrap' || s.format === 'emom') && !s.timeCapMin) {
        errs.push(`${where}: для ${s.format.toUpperCase()} потрібен time cap.`);
      }
      if (s.format === 'for_time' && !s.rounds) {
        errs.push(`${where}: для For Time потрібна кількість раундів.`);
      }
      if (s.rounds !== null && !Number.isInteger(s.rounds)) errs.push(`${where}: раунди мають бути цілим числом.`);
      if (s.rounds !== null && s.rounds <= 0) errs.push(`${where}: раунди мають бути більші за 0.`);
      if (s.timeCapMin !== null && s.timeCapMin <= 0) errs.push(`${where}: time cap має бути більший за 0.`);

      for (const it of s.items) {
        const w = `${where}, «${it.exercise.name}»`;
        if (it.exercise.modality !== 'M' && (!it.reps || it.reps <= 0 || !Number.isInteger(it.reps))) {
          errs.push(`${w}: вкажіть кількість повторів (ціле число).`);
        }
        if (it.exercise.modality === 'M' && !it.time && !it.calories && !it.distance) {
          errs.push(`${w}: вкажіть хоча б одне з: час, ккал, дистанція.`);
        }
        if (it.weight !== null && it.weight <= 0) errs.push(`${w}: вага має бути більша за 0.`);
        if (it.rpe !== null && (it.rpe < 1 || it.rpe > 10)) errs.push(`${w}: RPE має бути від 1 до 10.`);
        for (const [label, v] of [['час', it.time], ['ккал', it.calories], ['дистанція', it.distance]] as const) {
          if (v !== null && (v <= 0 || !Number.isInteger(v))) errs.push(`${w}: ${label} має бути цілим числом більше 0.`);
        }
      }
    });
    return errs;
  }

  private toPayload(): TrainingIn {
    return {
      title: this.title.trim(),
      date: this.date,
      comment: this.comment.trim() || undefined,
      sections: this.sections.map(
        (s): SectionIn => ({
          kind: s.kind,
          format: s.format,
          rounds: s.rounds ?? undefined,
          time_cap: s.timeCapMin ? Math.round(s.timeCapMin * 60) : undefined,
          comment: s.comment.trim() || undefined,
          items: s.items.map((it) => this.toSet(it)),
        }),
      ),
    };
  }

  private toSet(d: DraftSet): SetIn {
    const base = { exercise_id: d.exercise.id, comment: d.comment.trim() || undefined };
    switch (d.exercise.modality) {
      case 'G':
        return { ...base, type: 'G', reps: d.reps ?? 0, weight: d.weight ?? undefined, time: d.time ?? undefined };
      case 'W':
        return {
          ...base, type: 'W', reps: d.reps ?? 0, weight: d.weight ?? undefined,
          rpe: d.rpe ?? undefined, time: d.time ?? undefined,
        };
      case 'M':
        return {
          ...base, type: 'M', time: d.time ?? undefined,
          calories: d.calories ?? undefined, distance: d.distance ?? undefined,
        };
    }
  }
}
