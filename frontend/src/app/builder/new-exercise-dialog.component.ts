import { Component, HostListener, OnInit, computed, inject, input, output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../core/api.service';
import { CatalogService } from '../core/catalog.service';
import { errorMessage } from '../core/errors';
import { MODALITIES, PATTERNS, humanize } from '../core/format';
import { Exercise, Modality, MovementPattern } from '../core/models';

const UA_TO_LAT: Record<string, string> = {
  а: 'a', б: 'b', в: 'v', г: 'h', ґ: 'g', д: 'd', е: 'e', є: 'ie', ж: 'zh', з: 'z', и: 'y',
  і: 'i', ї: 'i', й: 'i', к: 'k', л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r', с: 's',
  т: 't', у: 'u', ф: 'f', х: 'kh', ц: 'ts', ч: 'ch', ш: 'sh', щ: 'shch', ю: 'iu', я: 'ia',
  ы: 'y', э: 'e', ё: 'e', ь: '', ъ: '', "'": '', '’': '', 'ʼ': '',
};
const DEFAULT_MUSCLES = [
  'core', 'quads', 'glutes', 'shoulders', 'hamstrings', 'triceps', 'forearms', 'upper_back',
  'traps', 'calves', 'lats', 'biceps', 'chest', 'lower_back', 'hip_flexors',
];

/** "Присідання з гантелею" -> "prysidannia-z-hantelieiu" (the API accepts only [a-z0-9-]). */
export function slugify(name: string): string {
  const latin = [...name.toLowerCase()].map((ch) => UA_TO_LAT[ch] ?? ch).join('');
  const slug = latin.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 120);
  return slug || 'exercise';
}

@Component({
  selector: 'app-new-exercise-dialog',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="modal" role="dialog" aria-modal="true" aria-label="Нова вправа">
      <button type="button" class="backdrop" aria-label="Закрити" (click)="dismissed.emit()"></button>
      <form class="x-card panel" (ngSubmit)="save()">
        <h3>Нова вправа</h3>

        <label class="field">
          <span>Назва *</span>
          <input class="x-input" name="name" maxlength="120" required [ngModel]="name" (ngModelChange)="onName($event)" />
        </label>

        <div class="row">
          <label class="field grow">
            <span>Тип *</span>
            <select class="x-input" name="modality" [(ngModel)]="modality">
              @for (m of modalities; track m.value) {
                <option [value]="m.value">{{ m.label }}</option>
              }
            </select>
          </label>
          <label class="field grow">
            <span>Патерн руху</span>
            <select class="x-input" name="pattern" [(ngModel)]="pattern">
              <option value="">Не вказано</option>
              @for (p of patterns; track p.value) {
                <option [value]="p.value">{{ p.label }}</option>
              }
            </select>
          </label>
        </div>

        <fieldset class="field">
          <legend>М'язи</legend>
          <div class="chips">
            @for (m of muscleOptions(); track m) {
              <button type="button" class="chip" [class.on]="muscles.includes(m)" [attr.aria-pressed]="muscles.includes(m)" (click)="toggle(muscles, m)">
                {{ humanize(m) }}
              </button>
            }
          </div>
        </fieldset>

        <fieldset class="field">
          <legend>Обладнання</legend>
          <div class="chips">
            @for (e of equipmentOptions(); track e) {
              <button type="button" class="chip" [class.on]="equipment.includes(e)" [attr.aria-pressed]="equipment.includes(e)" (click)="toggle(equipment, e)">
                {{ e }}
              </button>
            }
          </div>
          <input class="x-input" name="customEq" placeholder="Інше обладнання, натисніть Enter" [(ngModel)]="customEquipment" (keydown.enter)="addCustomEquipment($event)" />
        </fieldset>

        <label class="field">
          <span>Ідентифікатор (slug)</span>
          <input class="x-input" name="slug" maxlength="120" [ngModel]="slug" (ngModelChange)="onSlug($event)" />
          <small class="x-muted">Латиницею, цифри та дефіс. Формується з назви, за потреби змініть.</small>
        </label>

        @if (error) {
          <div class="x-error">{{ error }}</div>
        }

        <div class="actions">
          <button type="button" class="x-btn ghost" [disabled]="saving" (click)="dismissed.emit()">Скасувати</button>
          <button type="submit" class="x-btn primary" [disabled]="saving">
            {{ saving ? 'Збереження…' : 'Створити вправу' }}
          </button>
        </div>
      </form>
    </div>
  `,
  styles: [
    `
      .modal { position: fixed; inset: 0; z-index: 100; overflow: auto; display: flex; justify-content: center; align-items: flex-start; padding: 2rem 1rem; }
      .backdrop { position: fixed; inset: 0; border: 0; background: var(--x-backdrop); cursor: default; }
      .panel { position: relative; width: 100%; max-width: 560px; display: flex; flex-direction: column; gap: 0.9rem; box-shadow: var(--x-shadow); }
      h3 { margin: 0; font-size: 1.3rem; }
      .row { display: flex; gap: 0.8rem; flex-wrap: wrap; }
      .grow { flex: 1 1 200px; }
      .field { display: flex; flex-direction: column; gap: 0.3rem; font-size: 0.85rem; color: var(--x-muted); border: 0; padding: 0; margin: 0; min-width: 0; }
      legend { padding: 0; margin-bottom: 0.3rem; }
      .chips { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 0.4rem; }
      .chip {
        cursor: pointer; padding: 0.25rem 0.7rem; border-radius: 999px; font: inherit; font-size: 0.8rem;
        color: var(--x-text); background: var(--x-surface-2); border: 1px solid var(--x-border);
      }
      .chip:hover { background: var(--x-hover); }
      .chip.on { background: var(--x-accent); border-color: transparent; color: #fff; }
      .actions { display: flex; justify-content: flex-end; gap: 0.7rem; }
    `,
  ],
})
export class NewExerciseDialogComponent implements OnInit {
  readonly initialName = input('');
  readonly created = output<Exercise>();
  readonly dismissed = output<void>();

  private api = inject(ApiService);
  private catalog = inject(CatalogService);

  readonly modalities = MODALITIES;
  readonly patterns = PATTERNS;
  readonly humanize = humanize;

  readonly muscleOptions = computed(() =>
    [...new Set([...DEFAULT_MUSCLES, ...this.catalog.exercises().flatMap((e) => e.muscle_groups)])].sort(),
  );
  readonly equipmentOptions = computed(() =>
    [...new Set([...this.catalog.exercises().flatMap((e) => e.equipment), ...this.extraEquipment])].sort(),
  );

  name = '';
  slug = '';
  modality: Modality = 'W';
  pattern: MovementPattern | '' = '';
  muscles: string[] = [];
  equipment: string[] = [];
  customEquipment = '';
  error = '';
  saving = false;

  private slugTouched = false;
  private extraEquipment: string[] = [];

  ngOnInit() {
    this.onName(this.initialName());
  }

  @HostListener('document:keydown.escape')
  onEscape() {
    this.dismissed.emit();
  }

  onName(value: string) {
    this.name = value;
    if (!this.slugTouched) this.slug = value.trim() ? slugify(value) : '';
  }

  onSlug(value: string) {
    this.slug = value;
    this.slugTouched = true;
  }

  toggle(list: string[], item: string) {
    const i = list.indexOf(item);
    if (i >= 0) list.splice(i, 1);
    else list.push(item);
  }

  addCustomEquipment(event: Event) {
    event.preventDefault(); // Enter must not submit the form
    const value = this.customEquipment.trim().toLowerCase();
    if (!value) return;
    if (!this.equipmentOptions().includes(value)) this.extraEquipment = [...this.extraEquipment, value];
    if (!this.equipment.includes(value)) this.equipment.push(value);
    this.customEquipment = '';
  }

  async save() {
    this.error = '';
    const name = this.name.trim();
    const slug = this.slug.trim();
    if (!name) {
      this.error = 'Вкажіть назву вправи.';
      return;
    }
    if (!/^[a-z0-9-]+$/.test(slug)) {
      this.error = 'Slug може містити лише малі латинські літери, цифри та дефіс.';
      return;
    }
    this.saving = true;
    try {
      const exercise = await firstValueFrom(
        this.api.createExercise({
          slug,
          name,
          modality: this.modality,
          movement_pattern: this.pattern || null,
          muscle_groups: this.muscles,
          equipment: this.equipment,
        }),
      );
      this.created.emit(exercise);
    } catch (e) {
      this.error = errorMessage(e);
    } finally {
      this.saving = false;
    }
  }
}
