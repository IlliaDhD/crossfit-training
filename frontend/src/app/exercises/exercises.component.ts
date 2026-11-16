import { Component, OnInit, WritableSignal, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CatalogService } from '../core/catalog.service';
import {
  MODALITIES, MODALITY_LABEL, PATTERNS, PATTERN_LABEL, humanize,
} from '../core/format';
import { Modality, MovementPattern } from '../core/models';

const PAGE_SIZE = 36;

@Component({
  selector: 'app-exercises',
  standalone: true,
  imports: [FormsModule],
  template: `
    <header class="head">
      <h2>Каталог вправ</h2>
      <p class="x-muted">Знайдено {{ filtered().length }} з {{ catalog.exercises().length }}</p>
    </header>

    <div class="toolbar">
      <input
        class="x-input search"
        type="search"
        placeholder="Пошук за назвою (можна українською)"
        aria-label="Пошук вправ"
        [ngModel]="query()"
        (ngModelChange)="set(query, $event)"
      />
      <div class="seg" role="group" aria-label="Тип вправи">
        <button type="button" class="x-btn small" [class.primary]="!modality()" (click)="set(modality, '')">
          Усі
        </button>
        @for (m of modalities; track m.value) {
          <button
            type="button"
            class="x-btn small"
            [class.primary]="modality() === m.value"
            (click)="set(modality, m.value)"
          >
            {{ m.label }}
          </button>
        }
      </div>
      <select class="x-input sel" aria-label="Патерн руху" [ngModel]="pattern()" (ngModelChange)="set(pattern, $event)">
        <option value="">Усі рухи</option>
        @for (p of patterns; track p.value) {
          <option [value]="p.value">{{ p.label }}</option>
        }
      </select>
      <select class="x-input sel" aria-label="Група м'язів" [ngModel]="muscle()" (ngModelChange)="set(muscle, $event)">
        <option value="">Усі м'язи</option>
        @for (m of muscles(); track m) {
          <option [value]="m">{{ humanize(m) }}</option>
        }
      </select>
      <select class="x-input sel" aria-label="Обладнання" [ngModel]="equipment()" (ngModelChange)="set(equipment, $event)">
        <option value="">Усе обладнання</option>
        @for (e of equipments(); track e) {
          <option [value]="e">{{ e }}</option>
        }
      </select>
      @if (hasFilters()) {
        <button type="button" class="x-btn small ghost" (click)="reset()">Скинути</button>
      }
    </div>

    @if (catalog.error(); as err) {
      <div class="x-error">
        {{ err }}
        <button type="button" class="x-btn small" (click)="catalog.load(true)">Спробувати ще</button>
      </div>
    }
    @if (catalog.loading() && catalog.exercises().length === 0) {
      <p class="x-muted">Завантаження каталогу…</p>
    }

    <div class="grid">
      @for (ex of shown(); track ex.id) {
        <button
          type="button"
          class="x-card ex"
          [class.open]="expandedId() === ex.id"
          [attr.aria-expanded]="expandedId() === ex.id"
          (click)="toggle(ex.id)"
        >
          <span class="top">
            <span class="name">{{ ex.name }}</span>
            <span class="x-badge" [attr.data-m]="ex.modality">{{ modalityLabel[ex.modality] }}</span>
          </span>
          <span class="x-muted sub">
            {{ ex.movement_pattern ? patternLabel[ex.movement_pattern] : 'Без патерну' }}
          </span>
          <span class="chips">
            @for (m of expandedId() === ex.id ? ex.muscle_groups : ex.muscle_groups.slice(0, 3); track m) {
              <span class="x-chip">{{ humanize(m) }}</span>
            }
            @if (expandedId() !== ex.id && ex.muscle_groups.length > 3) {
              <span class="x-chip">+{{ ex.muscle_groups.length - 3 }}</span>
            }
          </span>
          @if (expandedId() === ex.id) {
            <span class="more">
              <span class="x-muted">Обладнання:</span>
              {{ ex.equipment.length ? ex.equipment.join(', ') : 'не потрібне' }}
            </span>
          }
        </button>
      } @empty {
        @if (!catalog.loading() && !catalog.error()) {
          <div class="x-card x-empty wide">Нічого не знайдено. Спробуйте змінити фільтри.</div>
        }
      }
    </div>

    @if (filtered().length > visible()) {
      <div class="more-wrap">
        <button type="button" class="x-btn" (click)="visible.set(visible() + PAGE_SIZE)">
          Показати ще ({{ filtered().length - visible() }})
        </button>
      </div>
    }
  `,
  styles: [
    `
      .head h2 { margin: 0 0 0.2rem; }
      .head p { margin: 0 0 1rem; }
      .toolbar { display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: center; margin-bottom: 1rem; }
      .search { flex: 1 1 260px; width: auto; }
      .sel { width: auto; flex: 0 1 190px; }
      .seg { display: flex; gap: 0.3rem; }
      .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 0.8rem; }
      .ex { display: flex; flex-direction: column; gap: 0.5rem; cursor: pointer; align-items: stretch; }
      .ex:hover, .ex.open { border-color: var(--x-border-strong); }
      .top { display: flex; justify-content: space-between; gap: 0.6rem; align-items: flex-start; }
      .name { font-weight: 700; }
      .sub { font-size: 0.85rem; }
      .chips { display: flex; flex-wrap: wrap; gap: 0.3rem; }
      .more { font-size: 0.85rem; }
      .wide { grid-column: 1 / -1; }
      .more-wrap { text-align: center; margin-top: 1.2rem; }
    `,
  ],
})
export class ExercisesComponent implements OnInit {
  readonly catalog = inject(CatalogService);

  readonly modalities = MODALITIES;
  readonly patterns = PATTERNS;
  readonly modalityLabel = MODALITY_LABEL;
  readonly patternLabel = PATTERN_LABEL;
  readonly humanize = humanize;
  readonly PAGE_SIZE = PAGE_SIZE;

  readonly query = signal('');
  readonly modality = signal<Modality | ''>('');
  readonly pattern = signal<MovementPattern | ''>('');
  readonly muscle = signal('');
  readonly equipment = signal('');
  readonly visible = signal(PAGE_SIZE);
  readonly expandedId = signal<string | null>(null);

  readonly muscles = computed(() => this.unique((e) => e.muscle_groups));
  readonly equipments = computed(() => this.unique((e) => e.equipment));

  readonly filtered = computed(() => {
    const q = this.query().trim().toLowerCase();
    const modality = this.modality();
    const pattern = this.pattern();
    const muscle = this.muscle();
    const equipment = this.equipment();
    return this.catalog.exercises().filter(
      (e) =>
        (!modality || e.modality === modality) &&
        (!pattern || e.movement_pattern === pattern) &&
        (!muscle || e.muscle_groups.includes(muscle)) &&
        (!equipment || e.equipment.includes(equipment)) &&
        (!q || e.name.toLowerCase().includes(q) || e.search_terms.some((t) => t.includes(q))),
    );
  });
  readonly shown = computed(() => this.filtered().slice(0, this.visible()));
  readonly hasFilters = computed(
    () => !!(this.query() || this.modality() || this.pattern() || this.muscle() || this.equipment()),
  );

  ngOnInit() {
    this.catalog.load();
  }

  /** Sets a filter and goes back to the first page of results. */
  set<T>(target: WritableSignal<T>, value: T) {
    target.set(value);
    this.visible.set(PAGE_SIZE);
  }

  reset() {
    this.set(this.query, '');
    this.modality.set('');
    this.pattern.set('');
    this.muscle.set('');
    this.equipment.set('');
  }

  toggle(id: string) {
    this.expandedId.set(this.expandedId() === id ? null : id);
  }

  private unique(pick: (e: { muscle_groups: string[]; equipment: string[] }) => string[]): string[] {
    return [...new Set(this.catalog.exercises().flatMap(pick))].sort();
  }
}
