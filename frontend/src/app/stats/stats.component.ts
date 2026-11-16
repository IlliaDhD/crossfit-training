import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../core/api.service';
import { CatalogService } from '../core/catalog.service';
import { errorMessage } from '../core/errors';
import {
  PATTERN_LABEL, formatDateShort, formatDuration, formatNumber, toIsoDate,
} from '../core/format';
import {
  DistanceBest, MovementPattern, RelativeStrengthPoint, StrengthRecord, TonnageGroup, TonnagePoint,
} from '../core/models';
import { ChartPoint, LineChartComponent } from '../shared/line-chart.component';

type Tab = 'tonnage' | 'relative' | 'records' | 'distance';

@Component({
  selector: 'app-stats',
  standalone: true,
  imports: [FormsModule, RouterLink, LineChartComponent],
  template: `
    <header class="head">
      <h2>Статистика</h2>
      <p class="x-muted">Розраховується з ваших збережених тренувань.</p>
    </header>

    <div class="seg" role="tablist" aria-label="Розділи статистики">
      @for (t of tabs; track t.id) {
        <button type="button" role="tab" class="x-btn small" [class.primary]="tab() === t.id" [attr.aria-selected]="tab() === t.id" (click)="setTab(t.id)">
          {{ t.label }}
        </button>
      }
    </div>

    @if (tab() !== 'distance') {
      <div class="filters">
        <label class="field">
          <span>З</span>
          <input class="x-input" type="date" [(ngModel)]="dateFrom" (ngModelChange)="reload()" />
        </label>
        <label class="field">
          <span>По</span>
          <input class="x-input" type="date" [(ngModel)]="dateTo" (ngModelChange)="reload()" />
        </label>
        <div class="presets">
          <button type="button" class="x-btn small ghost" (click)="preset(30)">30 днів</button>
          <button type="button" class="x-btn small ghost" (click)="preset(90)">90 днів</button>
          <button type="button" class="x-btn small ghost" (click)="preset(365)">Рік</button>
          <button type="button" class="x-btn small ghost" (click)="preset(0)">Увесь час</button>
        </div>
      </div>
    }

    @if (error()) {
      <div class="x-error">{{ error() }}</div>
    }

    @switch (tab()) {
      @case ('tonnage') {
        <section class="x-card">
          <div class="bar-head">
            <h3>Тоннаж</h3>
            <label class="field inline">
              <span class="sr">Групування</span>
              <select class="x-input" [(ngModel)]="groupBy" (ngModelChange)="reload()">
                <option value="week">По тижнях</option>
                <option value="exercise">По вправах</option>
                <option value="movement_pattern">По патернах руху</option>
              </select>
            </label>
          </div>
          <p class="x-muted note">Сума «повтори × вага» по силових підходах, у кілограмах.</p>
          @for (r of tonnageView(); track r.label) {
            <div class="bar-row">
              <span class="bar-label">{{ r.label }}</span>
              <span class="bar-track"><span class="bar-fill" [style.width.%]="r.pct"></span></span>
              <span class="bar-val">{{ fmt(r.tonnage, 0) }} кг <small class="x-muted">· {{ r.sets }} підх.</small></span>
            </div>
          } @empty {
            @if (!loading()) {
              <p class="x-muted empty">За цей період немає силових підходів із вагою.</p>
            }
          }
        </section>
      }

      @case ('relative') {
        <section class="x-card">
          <h3>Відносна сила</h3>
          <p class="x-muted note">
            Найкращий підхід за день, поділений на вашу вагу тіла. Вага береться із записів у
            <a routerLink="/profile">профілі</a>.
          </p>
          <div class="filters inner">
            <label class="field grow">
              <span>Вправа</span>
              <select class="x-input" [(ngModel)]="rsExercise" (ngModelChange)="reload()">
                <option value="">Оберіть вправу…</option>
                @for (e of strengthExercises(); track e.id) {
                  <option [value]="e.id">{{ e.name }}</option>
                }
              </select>
            </label>
            <label class="field">
              <span>Повторів</span>
              <input class="x-input" type="number" min="1" [(ngModel)]="rsReps" (ngModelChange)="reload()" />
            </label>
          </div>

          @if (!rsExercise || !rsReps) {
            <p class="x-muted empty">Оберіть вправу та кількість повторів.</p>
          } @else {
            @if (rsChart().length) {
              <app-line-chart [points]="rsChart()" unit="× ваги тіла" [decimals]="2" label="Відносна сила" />
            }
            @if (rsMissing() > 0) {
              <p class="warn">
                Для {{ rsMissing() }} підходів немає запису ваги на цю дату або раніше.
                <a routerLink="/profile">Додайте вагу</a>, щоб їх врахувати.
              </p>
            }
            @if (rsPoints().length) {
              <table class="table">
                <thead>
                  <tr><th>Дата</th><th class="num">Вага на штанзі</th><th class="num">Вага тіла</th><th class="num">Відносна сила</th></tr>
                </thead>
                <tbody>
                  @for (p of rsRows(); track p.training_id + p.date) {
                    <tr>
                      <td>{{ shortDate(p.date) }}</td>
                      <td class="num">{{ fmt(p.weight_kg) }} кг</td>
                      <td class="num">{{ p.body_weight_kg !== null ? fmt(p.body_weight_kg) + ' кг' : '—' }}</td>
                      <td class="num">{{ p.relative_strength !== null ? fmt(p.relative_strength, 2) + '×' : 'немає даних' }}</td>
                    </tr>
                  }
                </tbody>
              </table>
            } @else if (!loading()) {
              <p class="x-muted empty">Немає підходів цієї вправи з таким числом повторів.</p>
            }
          }
        </section>
      }

      @case ('records') {
        <section class="x-card">
          <h3>Рекорди</h3>
          <p class="x-muted note">Кожен новий максимум по вправі та точній кількості повторів.</p>
          <div class="filters inner">
            <label class="field grow">
              <span>Вправа</span>
              <select class="x-input" [(ngModel)]="recExercise" (ngModelChange)="reload()">
                <option value="">Усі вправи</option>
                @for (e of strengthExercises(); track e.id) {
                  <option [value]="e.id">{{ e.name }}</option>
                }
              </select>
            </label>
            <label class="field">
              <span>Повторів</span>
              <input class="x-input" type="number" min="1" placeholder="будь-яка" [(ngModel)]="recReps" (ngModelChange)="reload()" />
            </label>
          </div>
          @if (records().length) {
            <table class="table">
              <thead>
                <tr><th>Дата</th><th>Вправа</th><th class="num">Повтори</th><th class="num">Вага</th><th class="num">Приріст</th></tr>
              </thead>
              <tbody>
                @for (r of recordRows(); track r.training_id + r.exercise_id + r.reps) {
                  <tr>
                    <td>{{ shortDate(r.date) }}</td>
                    <td>{{ r.exercise_name }}</td>
                    <td class="num">{{ r.reps }}</td>
                    <td class="num">{{ fmt(r.weight_kg) }} кг</td>
                    <td class="num">
                      @if (r.improvement_kg !== null) {
                        <span class="up">+{{ fmt(r.improvement_kg) }} кг</span>
                      } @else {
                        <span class="x-muted">перший рекорд</span>
                      }
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          } @else if (!loading()) {
            <p class="x-muted empty">Рекордів поки немає.</p>
          }
        </section>
      }

      @case ('distance') {
        <section class="x-card">
          <h3>Найкращі результати на дистанціях</h3>
          <p class="x-muted note">Найкращий час для кожної пари «вправа + дистанція» (кардіо).</p>
          <div class="filters inner">
            <label class="field grow">
              <span>Вправа</span>
              <select class="x-input" [(ngModel)]="distExercise" (ngModelChange)="reload()">
                <option value="">Усі вправи</option>
                @for (e of cardioExercises(); track e.id) {
                  <option [value]="e.id">{{ e.name }}</option>
                }
              </select>
            </label>
          </div>
          @if (bests().length) {
            <table class="table">
              <thead>
                <tr><th>Вправа</th><th class="num">Дистанція</th><th class="num">Час</th><th class="num">Дата</th></tr>
              </thead>
              <tbody>
                @for (b of bests(); track b.exercise_id + b.distance) {
                  <tr>
                    <td>{{ b.exercise_name }}</td>
                    <td class="num">{{ fmt(b.distance, 0) }} м</td>
                    <td class="num">{{ duration(b.time_seconds) }}</td>
                    <td class="num">{{ shortDate(b.date) }}</td>
                  </tr>
                }
              </tbody>
            </table>
          } @else if (!loading()) {
            <p class="x-muted empty">Немає кардіо-підходів із часом і дистанцією.</p>
          }
        </section>
      }
    }

    @if (loading()) {
      <p class="x-muted">Завантаження…</p>
    }
  `,
  styles: [
    `
      .head h2 { margin: 0 0 0.2rem; }
      .head p { margin: 0 0 1rem; }
      h3 { margin: 0; font-size: 1.05rem; }
      .seg { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 1rem; }
      .filters { display: flex; flex-wrap: wrap; gap: 0.8rem; align-items: flex-end; margin-bottom: 1rem; }
      .filters.inner { margin: 0.6rem 0 1rem; }
      .field { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.8rem; color: var(--x-muted); }
      .field.grow { flex: 1 1 240px; }
      .field.inline { min-width: 190px; }
      .sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
      .presets { display: flex; gap: 0.3rem; flex-wrap: wrap; }
      .bar-head { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; }
      .note { margin: 0.3rem 0 1rem; font-size: 0.85rem; }
      .note a, .warn a { color: var(--x-accent); }
      .empty { text-align: center; padding: 1.5rem 0; margin: 0; }
      .warn { margin: 0.8rem 0; padding: 0.6rem 0.8rem; border-radius: 10px; color: var(--x-warn); background: rgba(180, 83, 9, 0.1); font-size: 0.9rem; }
      .bar-row { display: grid; grid-template-columns: minmax(110px, 200px) 1fr minmax(120px, auto); gap: 0.8rem; align-items: center; padding: 0.35rem 0; }
      .bar-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .bar-track { height: 14px; border-radius: 7px; background: var(--x-overlay-2); overflow: hidden; }
      .bar-fill { display: block; height: 100%; border-radius: 7px; background: var(--x-accent); min-width: 3px; }
      .bar-val { text-align: right; white-space: nowrap; font-weight: 600; }
      .table { width: 100%; border-collapse: collapse; margin-top: 0.8rem; }
      .table th { text-align: left; font-size: 0.8rem; color: var(--x-muted); font-weight: 600; padding: 0.4rem 0.5rem; }
      .table td { padding: 0.5rem; border-top: 1px solid var(--x-border); }
      .table .num { text-align: right; white-space: nowrap; }
      .up { color: var(--x-ok); font-weight: 700; }
      @media (max-width: 700px) {
        .bar-row { grid-template-columns: 1fr; gap: 0.2rem; }
        .bar-val { text-align: left; }
      }
    `,
  ],
})
export class StatsComponent implements OnInit {
  private api = inject(ApiService);
  private catalog = inject(CatalogService);

  readonly tabs: { id: Tab; label: string }[] = [
    { id: 'tonnage', label: 'Тоннаж' },
    { id: 'relative', label: 'Відносна сила' },
    { id: 'records', label: 'Рекорди' },
    { id: 'distance', label: 'Дистанції' },
  ];
  readonly fmt = formatNumber;
  readonly shortDate = formatDateShort;
  readonly duration = formatDuration;

  readonly tab = signal<Tab>('tonnage');
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  dateFrom = '';
  dateTo = '';
  groupBy: TonnageGroup = 'week';
  rsExercise = '';
  rsReps: number | null = 5;
  recExercise = '';
  recReps: number | null = null;
  distExercise = '';

  readonly tonnageRows = signal<TonnagePoint[]>([]);
  readonly rsPoints = signal<RelativeStrengthPoint[]>([]);
  readonly records = signal<StrengthRecord[]>([]);
  readonly bests = signal<DistanceBest[]>([]);

  private requestId = 0;

  readonly strengthExercises = computed(() => this.catalog.exercises().filter((e) => e.modality === 'W'));
  readonly cardioExercises = computed(() => this.catalog.exercises().filter((e) => e.modality === 'M'));

  readonly tonnageView = computed(() => {
    const rows = this.tonnageRows();
    const max = rows.reduce((m, r) => Math.max(m, r.tonnage), 0);
    return rows.map((r) => ({
      label: this.tonnageLabel(r),
      tonnage: r.tonnage,
      sets: r.sets,
      pct: max ? (r.tonnage / max) * 100 : 0,
    }));
  });

  readonly rsChart = computed<ChartPoint[]>(() =>
    this.rsPoints()
      .filter((p) => p.status === 'ok' && p.relative_strength !== null)
      .map((p) => ({
        date: p.date,
        value: p.relative_strength as number,
        tip: `${formatDateShort(p.date)}: ${formatNumber(p.weight_kg)} кг / ${formatNumber(p.body_weight_kg ?? 0)} кг = ${formatNumber(p.relative_strength ?? 0, 2)}×`,
      })),
  );
  readonly rsMissing = computed(() => this.rsPoints().filter((p) => p.status !== 'ok').length);
  readonly rsRows = computed(() => [...this.rsPoints()].sort((a, b) => b.date.localeCompare(a.date)));
  readonly recordRows = computed(() =>
    [...this.records()].sort((a, b) => b.date.localeCompare(a.date) || a.exercise_name.localeCompare(b.exercise_name)),
  );

  ngOnInit() {
    this.catalog.load();
    this.reload();
  }

  setTab(tab: Tab) {
    this.tab.set(tab);
    this.reload();
  }

  preset(days: number) {
    const to = new Date();
    this.dateTo = days ? toIsoDate(to) : '';
    this.dateFrom = days ? toIsoDate(new Date(to.getFullYear(), to.getMonth(), to.getDate() - days)) : '';
    this.reload();
  }

  async reload() {
    this.error.set(null);
    if (this.dateFrom && this.dateTo && this.dateFrom > this.dateTo) {
      this.error.set('Дата «З» не може бути пізніше за дату «По».');
      return;
    }
    const range = { date_from: this.dateFrom || undefined, date_to: this.dateTo || undefined };
    const req = ++this.requestId;
    this.loading.set(true);
    try {
      switch (this.tab()) {
        case 'tonnage': {
          const rows = await firstValueFrom(this.api.tonnage({ group_by: this.groupBy, ...range }));
          if (req === this.requestId) this.tonnageRows.set(this.sortTonnage(rows));
          break;
        }
        case 'relative': {
          if (!this.rsExercise || !this.rsReps || this.rsReps <= 0) {
            this.rsPoints.set([]);
            break;
          }
          const rows = await firstValueFrom(
            this.api.relativeStrength({ exercise_id: this.rsExercise, reps: this.rsReps, ...range }),
          );
          if (req === this.requestId) this.rsPoints.set(rows);
          break;
        }
        case 'records': {
          const rows = await firstValueFrom(
            this.api.strengthRecords({
              exercise_id: this.recExercise || undefined,
              reps: this.recReps && this.recReps > 0 ? this.recReps : undefined,
              ...range,
            }),
          );
          if (req === this.requestId) this.records.set(rows);
          break;
        }
        case 'distance': {
          const rows = await firstValueFrom(
            this.api.distanceBests({ exercise_id: this.distExercise || undefined }),
          );
          if (req === this.requestId) this.bests.set(rows);
          break;
        }
      }
    } catch (e) {
      if (req === this.requestId) this.error.set(errorMessage(e));
    } finally {
      if (req === this.requestId) this.loading.set(false);
    }
  }

  private tonnageLabel(r: TonnagePoint): string {
    if (r.group_by === 'week') return `${r.year}, тиждень ${r.week}`;
    if (r.group_by === 'exercise') return r.exercise_name ?? '—';
    return r.movement_pattern ? PATTERN_LABEL[r.movement_pattern as MovementPattern] ?? r.movement_pattern : 'Без патерну';
  }

  private sortTonnage(rows: TonnagePoint[]): TonnagePoint[] {
    return [...rows].sort((a, b) =>
      a.group_by === 'week'
        ? (a.year ?? 0) - (b.year ?? 0) || (a.week ?? 0) - (b.week ?? 0)
        : b.tonnage - a.tonnage,
    );
  }
}
