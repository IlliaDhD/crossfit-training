import { Component, HostListener, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../core/api.service';
import { errorMessage } from '../core/errors';
import {
  KIND_LABEL, formatDateShort, parseIsoDate, plural, summarize, toIsoDate,
} from '../core/format';
import { Training } from '../core/models';
import { TrainingDetailComponent } from './training-detail.component';

interface Cell {
  iso: string;
  day: number;
  today: boolean;
  trainings: Training[];
}

const LIST_PAGE = 20;

@Component({
  selector: 'app-trainings',
  standalone: true,
  imports: [RouterLink, TrainingDetailComponent],
  template: `
    <header class="head">
      <div class="grow">
        <h2>Тренування</h2>
        <p class="x-muted">Натисніть на день із тренуванням, щоб побачити їх назви</p>
      </div>
      <div class="seg" role="group" aria-label="Вигляд">
        <button type="button" class="x-btn small" [class.primary]="mode() === 'calendar'" (click)="setMode('calendar')">Календар</button>
        <button type="button" class="x-btn small" [class.primary]="mode() === 'list'" (click)="setMode('list')">Список</button>
      </div>
      <a class="x-btn primary" routerLink="/builder">+ Нове тренування</a>
    </header>

    @if (error()) {
      <div class="x-error">{{ error() }}</div>
    }

    @if (mode() === 'calendar') {
      <section class="x-card cal" aria-label="Календар тренувань">
        <div class="cal-nav">
          <button type="button" class="x-btn ghost" aria-label="Попередній місяць" (click)="shiftMonth(-1)">‹</button>
          <strong class="month">{{ monthTitle() }}</strong>
          <button type="button" class="x-btn ghost" aria-label="Наступний місяць" (click)="shiftMonth(1)">›</button>
          <button type="button" class="x-btn ghost" (click)="goToday()">Сьогодні</button>
        </div>

        <div class="dow">
          @for (d of dows; track d) {
            <span>{{ d }}</span>
          }
        </div>

        @if (popoverDay()) {
          <button type="button" class="scrim" aria-label="Закрити" (click)="popoverDay.set(null)"></button>
        }

        @for (week of weeks(); track $index) {
          <div class="week">
            @for (c of week; track $index; let col = $index) {
              @if (!c) {
                <div class="cell blank"></div>
              } @else if (c.trainings.length) {
                <div class="cell" [class.open]="popoverDay() === c.iso">
                  <button
                    type="button"
                    class="day has"
                    [class.today]="c.today"
                    [attr.aria-expanded]="popoverDay() === c.iso"
                    (click)="togglePopover(c.iso)"
                  >
                    <span class="num">{{ c.day }}</span>
                    <span class="badge">🏋 {{ c.trainings.length }}</span>
                  </button>
                  @if (popoverDay() === c.iso) {
                    <div class="pop" [class.right]="col >= 4" role="dialog" aria-label="Тренування за день">
                      <p class="pop-title">{{ dayTitle(c.iso) }}</p>
                      @for (t of c.trainings; track t.id) {
                        <button type="button" class="pop-item" (click)="open(t)">
                          <span class="pop-name">{{ t.title }}</span>
                          <small class="x-muted">
                            {{ summary(t).sets }} {{ plural(summary(t).sets, ['підхід', 'підходи', 'підходів']) }}
                          </small>
                        </button>
                      }
                    </div>
                  }
                </div>
              } @else {
                <div class="cell">
                  <div class="day" [class.today]="c.today"><span class="num">{{ c.day }}</span></div>
                </div>
              }
            }
          </div>
        }

        @if (!loading() && monthItems().length === 0) {
          <p class="x-muted none">
            У цьому місяці тренувань немає. <a routerLink="/builder">Створити тренування</a>
          </p>
        }
      </section>
    } @else {
      @if (loading() && listItems().length === 0) {
        <p class="x-muted">Завантаження…</p>
      }
      <div class="cards">
        @for (t of listItems(); track t.id) {
          <button type="button" class="x-card tcard" (click)="open(t)">
            <span class="t-top">
              <strong>{{ t.title }}</strong>
              <span class="x-muted">{{ shortDate(t.date) }}</span>
            </span>
            <span class="chips">
              @for (k of summary(t).kinds; track k) {
                <span class="x-chip">{{ kindLabel[k] }}</span>
              }
            </span>
            <span class="x-muted small">
              {{ summary(t).sections }} {{ plural(summary(t).sections, ['секція', 'секції', 'секцій']) }} ·
              {{ summary(t).sets }} {{ plural(summary(t).sets, ['підхід', 'підходи', 'підходів']) }}
            </span>
            <span class="small">{{ summary(t).exercises }}</span>
          </button>
        } @empty {
          @if (!loading() && !error()) {
            <div class="x-card x-empty wide">
              Тренувань поки немає. <a routerLink="/builder">Створити тренування</a>
            </div>
          }
        }
      </div>
      @if (listItems().length < listTotal()) {
        <div class="more-wrap">
          <button type="button" class="x-btn" [disabled]="loading()" (click)="loadList(false)">
            Показати ще ({{ listTotal() - listItems().length }})
          </button>
        </div>
      }
    }

    @if (selected(); as t) {
      <div class="modal" role="dialog" aria-modal="true" aria-label="Деталі тренування">
        <button type="button" class="backdrop" aria-label="Закрити" (click)="close()"></button>
        <div class="panel">
          <button type="button" class="x-btn small ghost close" (click)="close()">✕ Закрити</button>
          <app-training-detail [training]="t" (remove)="deleteTraining(t)" />
        </div>
      </div>
    }
  `,
  styles: [
    `
      .head { display: flex; flex-wrap: wrap; gap: 1rem; align-items: center; margin-bottom: 1rem; }
      .grow { flex: 1; }
      .head h2 { margin: 0 0 0.2rem; }
      .head p { margin: 0; }
      .seg { display: flex; gap: 0.3rem; }
      .cal { padding: 1.2rem; position: relative; }
      .cal-nav { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem; }
      .month { flex: 1; text-align: center; font-size: 1.3rem; text-transform: capitalize; }
      .dow, .week { display: grid; grid-template-columns: repeat(7, 1fr); gap: 0.5rem; }
      .dow { margin-bottom: 0.5rem; text-align: center; color: var(--x-muted); font-weight: 600; }
      .week { margin-bottom: 0.5rem; }
      .cell { position: relative; }
      .cell.open { z-index: 30; }
      .day {
        box-sizing: border-box; width: 100%; min-height: 104px; display: flex; flex-direction: column;
        justify-content: space-between; align-items: flex-start; padding: 0.6rem 0.7rem;
        border-radius: 14px; border: 1px solid var(--x-border); background: var(--x-overlay);
        color: var(--x-text); font: inherit; text-align: left;
      }
      .num { font-size: 1.15rem; font-weight: 600; }
      .day.today { border-color: var(--x-ok); }
      .day.today .num { color: var(--x-ok); }
      button.day { cursor: pointer; }
      .day.has { background: var(--x-accent-soft); border-color: rgba(226, 53, 86, 0.45); }
      button.day:hover, .cell.open .day { background: rgba(226, 53, 86, 0.22); }
      .badge {
        align-self: flex-end; padding: 0.15rem 0.55rem; border-radius: 999px; font-size: 0.8rem;
        background: var(--x-accent); color: #fff; font-weight: 700;
      }
      .scrim { position: fixed; inset: 0; z-index: 20; border: 0; background: transparent; cursor: default; }
      .pop {
        position: absolute; top: calc(100% + 6px); left: 0; z-index: 40; min-width: 240px; max-width: 320px;
        padding: 0.7rem; border-radius: 14px; background: var(--x-surface-2);
        border: 1px solid var(--x-border-strong); box-shadow: var(--x-shadow);
      }
      .pop.right { left: auto; right: 0; }
      .pop-title { margin: 0 0 0.5rem; font-size: 0.8rem; color: var(--x-muted); text-transform: capitalize; }
      .pop-item {
        width: 100%; display: flex; flex-direction: column; gap: 0.1rem; text-align: left; cursor: pointer;
        padding: 0.5rem 0.6rem; border: none; border-radius: 10px; background: transparent;
        color: var(--x-text); font: inherit;
      }
      .pop-item:hover, .pop-item:focus-visible { background: var(--x-overlay-2); }
      .pop-name { font-weight: 700; }
      .none { margin: 0.5rem 0 0; text-align: center; }
      .none a, .x-empty a { color: var(--x-ok); }
      .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 0.8rem; }
      .wide { grid-column: 1 / -1; }
      .tcard { display: flex; flex-direction: column; gap: 0.4rem; cursor: pointer; align-items: stretch; }
      .tcard:hover { border-color: var(--x-accent); }
      .t-top { display: flex; justify-content: space-between; gap: 0.6rem; }
      .chips { display: flex; flex-wrap: wrap; gap: 0.3rem; }
      .small { font-size: 0.85rem; }
      .more-wrap { text-align: center; margin-top: 1rem; }
      .modal { position: fixed; inset: 0; z-index: 100; overflow: auto; display: flex; justify-content: center; align-items: flex-start; padding: 2rem 1rem; }
      .backdrop { position: fixed; inset: 0; border: 0; background: var(--x-backdrop); cursor: default; }
      .panel { position: relative; width: 100%; max-width: 720px; }
      .close { margin-bottom: 0.6rem; background: var(--x-surface-2); }
      @media (max-width: 700px) {
        .cal { padding: 0.6rem; }
        .dow, .week { gap: 0.25rem; }
        .day { min-height: 58px; padding: 0.3rem 0.4rem; border-radius: 10px; }
        .num { font-size: 0.95rem; }
        .badge { font-size: 0.65rem; padding: 0.05rem 0.35rem; }
        .pop { position: fixed; left: 1rem; right: 1rem; top: auto; bottom: 1rem; max-width: none; }
      }
    `,
  ],
})
export class TrainingsComponent implements OnInit {
  private api = inject(ApiService);
  private route = inject(ActivatedRoute);

  readonly dows = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд'];
  readonly kindLabel = KIND_LABEL;
  readonly summary = summarize;
  readonly plural = plural;
  readonly shortDate = formatDateShort;

  readonly mode = signal<'calendar' | 'list'>('calendar');
  readonly month = signal(this.startOfMonth(new Date()));
  readonly monthItems = signal<Training[]>([]);
  readonly listItems = signal<Training[]>([]);
  readonly listTotal = signal(0);
  readonly popoverDay = signal<string | null>(null);
  readonly selected = signal<Training | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  private requestId = 0;

  readonly monthTitle = computed(() =>
    this.month().toLocaleDateString('uk-UA', { month: 'long', year: 'numeric' }),
  );

  readonly weeks = computed<(Cell | null)[][]>(() => {
    const m = this.month();
    const y = m.getFullYear();
    const mo = m.getMonth();
    const lead = (new Date(y, mo, 1).getDay() + 6) % 7; // week starts on Monday
    const daysInMonth = new Date(y, mo + 1, 0).getDate();
    const byDate = new Map<string, Training[]>();
    for (const t of this.monthItems()) byDate.set(t.date, [...(byDate.get(t.date) ?? []), t]);
    const todayIso = toIsoDate(new Date());

    const cells: (Cell | null)[] = Array<Cell | null>(lead).fill(null);
    for (let d = 1; d <= daysInMonth; d++) {
      const iso = toIsoDate(new Date(y, mo, d));
      cells.push({ iso, day: d, today: iso === todayIso, trainings: byDate.get(iso) ?? [] });
    }
    while (cells.length % 7) cells.push(null);

    const weeks: (Cell | null)[][] = [];
    for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
    return weeks;
  });

  @HostListener('document:keydown.escape')
  onEscape() {
    if (this.selected()) this.close();
    else this.popoverDay.set(null);
  }

  async ngOnInit() {
    // After saving in the builder the user lands here with ?id=<new training>
    const id = this.route.snapshot.queryParamMap.get('id');
    if (id) {
      try {
        const t = await firstValueFrom(this.api.getTraining(id));
        this.selected.set(t);
        this.month.set(this.startOfMonth(parseIsoDate(t.date)));
      } catch (e) {
        this.error.set(errorMessage(e));
      }
    }
    await this.loadMonth();
  }

  // --------------------------------------------------------------- loading

  async loadMonth() {
    const m = this.month();
    const from = toIsoDate(new Date(m.getFullYear(), m.getMonth(), 1));
    const to = toIsoDate(new Date(m.getFullYear(), m.getMonth() + 1, 0));
    const req = ++this.requestId;
    this.loading.set(true);
    this.error.set(null);
    try {
      const page = await firstValueFrom(
        this.api.listTrainings({ date_from: from, date_to: to, limit: 100 }),
      );
      if (req === this.requestId) this.monthItems.set(page.items);
    } catch (e) {
      if (req === this.requestId) this.error.set(errorMessage(e));
    } finally {
      if (req === this.requestId) this.loading.set(false);
    }
  }

  async loadList(reset: boolean) {
    const offset = reset ? 0 : this.listItems().length;
    this.loading.set(true);
    this.error.set(null);
    try {
      const page = await firstValueFrom(this.api.listTrainings({ limit: LIST_PAGE, offset }));
      this.listItems.set(reset ? page.items : [...this.listItems(), ...page.items]);
      this.listTotal.set(page.total);
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.loading.set(false);
    }
  }

  // ----------------------------------------------------------- interaction

  setMode(mode: 'calendar' | 'list') {
    this.mode.set(mode);
    this.popoverDay.set(null);
    if (mode === 'list') this.loadList(true);
    else this.loadMonth();
  }

  shiftMonth(delta: number) {
    const m = this.month();
    this.month.set(new Date(m.getFullYear(), m.getMonth() + delta, 1));
    this.popoverDay.set(null);
    this.loadMonth();
  }

  goToday() {
    this.month.set(this.startOfMonth(new Date()));
    this.popoverDay.set(null);
    this.loadMonth();
  }

  togglePopover(iso: string) {
    this.popoverDay.set(this.popoverDay() === iso ? null : iso);
  }

  dayTitle(iso: string): string {
    return parseIsoDate(iso).toLocaleDateString('uk-UA', {
      weekday: 'long', day: 'numeric', month: 'long',
    });
  }

  open(t: Training) {
    this.popoverDay.set(null);
    this.selected.set(t);
  }

  close() {
    this.selected.set(null);
  }

  async deleteTraining(t: Training) {
    if (!window.confirm(`Видалити тренування «${t.title}»?`)) return;
    try {
      await firstValueFrom(this.api.deleteTraining(t.id));
      this.selected.set(null);
      this.monthItems.update((list) => list.filter((x) => x.id !== t.id));
      this.listItems.update((list) => list.filter((x) => x.id !== t.id));
      this.listTotal.update((n) => Math.max(0, n - 1));
    } catch (e) {
      this.error.set(errorMessage(e));
    }
  }

  private startOfMonth(d: Date): Date {
    return new Date(d.getFullYear(), d.getMonth(), 1);
  }
}
