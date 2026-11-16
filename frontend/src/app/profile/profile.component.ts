import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import Keycloak from 'keycloak-js';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../core/api.service';
import { errorMessage } from '../core/errors';
import {
  ageFromBirth, bmi, formatDateLong, formatDateShort, formatNumber, plural, toIsoDate,
} from '../core/format';
import { AthleteProfile, BodyMeasurement } from '../core/models';
import { ChartPoint, LineChartComponent } from '../shared/line-chart.component';

const ROLE_LABEL: Record<string, string> = { coach: 'Тренер', athlete: 'Атлет' };

function hash(text: string): number {
  let h = 0;
  for (const ch of text) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return h;
}

function bmiCategory(value: number): { label: string; tone: 'low' | 'ok' | 'high' } {
  if (value < 18.5) return { label: 'Недостатня вага', tone: 'low' };
  if (value < 25) return { label: 'Норма', tone: 'ok' };
  if (value < 30) return { label: 'Надлишкова вага', tone: 'high' };
  return { label: 'Ожиріння', tone: 'high' };
}

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [FormsModule, LineChartComponent],
  template: `
    <section class="x-card hero">
      <div class="avatar" aria-hidden="true" [style.background]="avatarBackground">{{ initials }}</div>
      <div class="who">
        <h2>{{ displayName }}</h2>
        @if (email) {
          <p class="x-muted email">{{ email }}</p>
        }
        <div class="roles">
          @for (r of roles; track r) {
            <span class="role">{{ r }}</span>
          }
        </div>
      </div>
      <div class="tiles">
        <div class="tile">
          <span class="ico" aria-hidden="true">🎂</span>
          <b>{{ age() !== null ? age() : '—' }}</b>
          <small>{{ age() !== null ? yearsWord() : 'вік' }}</small>
        </div>
        <div class="tile">
          <span class="ico" aria-hidden="true">📏</span>
          <b>{{ profile()?.height_cm ? fmt(profile()!.height_cm!) : '—' }}</b>
          <small>см зріст</small>
        </div>
        <div class="tile">
          <span class="ico" aria-hidden="true">⚖️</span>
          <b>{{ profile()?.current_weight_kg ? fmt(profile()!.current_weight_kg!) : '—' }}</b>
          <small>кг {{ profile()?.current_weight_date ? '· ' + shortDate(profile()!.current_weight_date!) : 'вага' }}</small>
        </div>
        <div class="tile" [attr.data-tone]="bmiInfo()?.tone">
          <span class="ico" aria-hidden="true">💪</span>
          <b>{{ bmiInfo() ? bmiInfo()!.value : '—' }}</b>
          <small>{{ bmiInfo() ? 'ІМТ · ' + bmiInfo()!.label : 'ІМТ' }}</small>
        </div>
      </div>
    </section>

    @if (error()) {
      <div class="x-error">{{ error() }}</div>
    }
    @if (notice()) {
      <div class="notice">{{ notice() }}</div>
    }

    <div class="cols">
      <section class="x-card">
        <h3>Особисті дані</h3>
        <form class="form" (ngSubmit)="saveProfile()">
          <label class="field">
            <span>Дата народження</span>
            <input class="x-input" type="date" name="birth" [max]="today" [(ngModel)]="birth" />
          </label>
          <label class="field">
            <span>Зріст, см</span>
            <input class="x-input" type="number" name="height" min="1" step="0.5" [(ngModel)]="height" />
          </label>
          <button type="submit" class="x-btn primary full" [disabled]="savingProfile()">
            {{ savingProfile() ? 'Збереження…' : 'Зберегти дані' }}
          </button>
        </form>
      </section>

      <section class="x-card">
        <h3>Записати вагу</h3>
        <form class="form" (ngSubmit)="saveMeasurement()">
          <label class="field">
            <span>Дата</span>
            <input class="x-input" type="date" name="mdate" [max]="today" [(ngModel)]="mDate" />
          </label>
          <label class="field">
            <span>Вага, кг</span>
            <input class="x-input" type="number" name="mweight" min="1" step="0.1" [(ngModel)]="mWeight" />
          </label>
          <button type="submit" class="x-btn primary full" [disabled]="savingWeight()">
            {{ savingWeight() ? 'Збереження…' : 'Зберегти вагу' }}
          </button>
        </form>
        <p class="x-muted hint">Одна вага на день: запис на ту саму дату замінює попередній.</p>
      </section>
    </div>

    <section class="x-card block">
      <h3>Динаміка ваги</h3>
      @if (summary(); as s) {
        <div class="summary">
          <div><small>Перший запис</small><b>{{ fmt(s.first) }} кг</b></div>
          <div><small>Зараз</small><b>{{ fmt(s.last) }} кг</b></div>
          <div>
            <small>Зміна</small>
            <b [class.up]="s.delta > 0" [class.down]="s.delta < 0">{{ s.delta > 0 ? '+' : '' }}{{ fmt(s.delta) }} кг</b>
          </div>
          <div><small>Мін. / макс.</small><b>{{ fmt(s.min) }} / {{ fmt(s.max) }}</b></div>
          <div><small>Середня</small><b>{{ fmt(s.avg) }} кг</b></div>
        </div>
        <app-line-chart [points]="chartPoints()" unit="кг" [decimals]="1" label="Динаміка ваги" />
      } @else if (!loading()) {
        <p class="x-muted empty">Ще немає записів ваги. Додайте першу вище.</p>
      }
    </section>

    @if (rows().length) {
      <section class="x-card block">
        <h3>Історія записів ({{ rows().length }})</h3>
        <table class="table">
          <thead>
            <tr><th>Дата</th><th class="num">Вага</th><th></th></tr>
          </thead>
          <tbody>
            @for (m of rows(); track m.date) {
              <tr>
                <td>{{ longDate(m.date) }}</td>
                <td class="num">{{ fmt(m.weight_kg) }} кг</td>
                <td class="actions">
                  <button type="button" class="x-btn small ghost" (click)="edit(m)">Редагувати</button>
                  <button type="button" class="x-btn small danger" (click)="remove(m)">Видалити</button>
                </td>
              </tr>
            }
          </tbody>
        </table>
      </section>
    }
  `,
  styles: [
    `
      h2 { margin: 0; font-size: 1.6rem; }
      h3 { margin: 0 0 0.9rem; font-size: 1.05rem; }
      .hero { display: flex; flex-wrap: wrap; gap: 1.5rem; align-items: center; margin-bottom: 1rem; padding: 1.5rem; }
      .avatar {
        width: 92px; height: 92px; border-radius: 50%; display: grid; place-items: center; flex: none;
        font-size: 2.1rem; font-weight: 800; color: #fff; letter-spacing: 0.03em;
        box-shadow: 0 8px 22px rgba(24, 32, 80, 0.25);
      }
      .who { flex: 1 1 200px; min-width: 0; }
      .email { margin: 0.2rem 0 0.6rem; overflow-wrap: anywhere; }
      .roles { display: flex; gap: 0.4rem; flex-wrap: wrap; }
      .role {
        padding: 0.15rem 0.8rem; border-radius: 999px; font-size: 0.8rem; font-weight: 700;
        color: var(--x-accent); background: var(--x-accent-soft);
      }
      .tiles { display: grid; grid-template-columns: repeat(4, minmax(96px, 1fr)); gap: 0.7rem; flex: 2 1 420px; }
      .tile {
        display: flex; flex-direction: column; align-items: center; gap: 0.15rem; text-align: center;
        padding: 0.8rem 0.4rem; border-radius: 16px; background: var(--x-overlay); border: 1px solid var(--x-border);
      }
      .tile .ico { font-size: 1.3rem; }
      .tile b { font-size: 1.5rem; line-height: 1.1; }
      .tile small { color: var(--x-muted); font-size: 0.75rem; }
      .tile[data-tone='ok'] { border-color: rgba(11, 143, 106, 0.5); background: rgba(11, 143, 106, 0.08); }
      .tile[data-tone='high'], .tile[data-tone='low'] { border-color: rgba(180, 83, 9, 0.45); background: rgba(180, 83, 9, 0.07); }
      .cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
      .form { display: flex; flex-direction: column; gap: 0.8rem; }
      .field { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.8rem; color: var(--x-muted); }
      .full { width: 100%; }
      .hint { margin: 0.8rem 0 0; font-size: 0.85rem; }
      .block { margin-bottom: 1rem; }
      .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 0.6rem; margin-bottom: 1rem; }
      .summary div { display: flex; flex-direction: column; padding: 0.6rem 0.8rem; border-radius: 12px; background: var(--x-overlay); }
      .summary small { color: var(--x-muted); font-size: 0.75rem; }
      .summary b { font-size: 1.1rem; }
      .summary b.up { color: #b45309; }
      .summary b.down { color: var(--x-ok); }
      .empty { text-align: center; padding: 1.5rem 0; margin: 0; }
      .notice {
        margin-bottom: 1rem; padding: 0.7rem 1rem; border-radius: 12px; color: #08694f;
        background: rgba(11, 143, 106, 0.12); border: 1px solid rgba(11, 143, 106, 0.4);
      }
      .x-error { margin-bottom: 1rem; }
      .table { width: 100%; border-collapse: collapse; }
      .table th { text-align: left; font-size: 0.8rem; color: var(--x-muted); font-weight: 600; padding: 0.4rem 0.5rem; }
      .table td { padding: 0.5rem; border-top: 1px solid var(--x-border); }
      .table .num { text-align: right; white-space: nowrap; }
      .actions { display: flex; gap: 0.3rem; justify-content: flex-end; }
      @media (max-width: 700px) {
        .hero { padding: 1rem; justify-content: center; text-align: center; }
        .roles { justify-content: center; }
        .tiles { grid-template-columns: repeat(2, 1fr); }
      }
    `,
  ],
})
export class ProfileComponent implements OnInit {
  private api = inject(ApiService);
  private keycloak = inject(Keycloak);

  readonly today = toIsoDate(new Date());
  readonly fmt = formatNumber;
  readonly shortDate = formatDateShort;
  readonly longDate = formatDateLong;

  // identity comes from the Keycloak token; the avatar is generated from the name (no upload)
  private readonly claims = this.keycloak.tokenParsed ?? {};
  readonly username: string = this.claims['preferred_username'] ?? '';
  readonly displayName: string = this.claims['name'] || this.username || 'Користувач';
  readonly email: string = this.claims['email'] ?? '';
  readonly roles: string[] = ((this.claims['realm_access']?.roles as string[] | undefined) ?? [])
    .filter((r) => r in ROLE_LABEL)
    .map((r) => ROLE_LABEL[r]);
  readonly initials: string =
    this.displayName
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((w) => w[0])
      .join('')
      .toUpperCase() || '?';
  readonly avatarBackground: string = (() => {
    const h = hash(this.username || this.displayName) % 360;
    return `linear-gradient(135deg, hsl(${h} 72% 52%), hsl(${(h + 48) % 360} 72% 44%))`;
  })();

  readonly profile = signal<AthleteProfile | null>(null);
  readonly measurements = signal<BodyMeasurement[]>([]);
  readonly loading = signal(false);
  readonly savingProfile = signal(false);
  readonly savingWeight = signal(false);
  readonly error = signal<string | null>(null);
  readonly notice = signal<string | null>(null);

  birth = '';
  height: number | null = null;
  mDate = this.today;
  mWeight: number | null = null;

  readonly rows = computed(() => [...this.measurements()].sort((a, b) => b.date.localeCompare(a.date)));
  readonly chartPoints = computed<ChartPoint[]>(() =>
    this.measurements().map((m) => ({
      date: m.date,
      value: m.weight_kg,
      tip: `${formatDateShort(m.date)}: ${formatNumber(m.weight_kg)} кг`,
    })),
  );
  readonly age = computed(() => {
    const b = this.profile()?.birth_date;
    return b ? ageFromBirth(b) : null;
  });
  readonly yearsWord = computed(() => plural(this.age() ?? 0, ['рік', 'роки', 'років']));
  readonly bmiInfo = computed(() => {
    const p = this.profile();
    if (!p?.current_weight_kg || !p.height_cm) return null;
    const value = bmi(p.current_weight_kg, p.height_cm);
    return { value, ...bmiCategory(value) };
  });
  readonly summary = computed(() => {
    const sorted = [...this.measurements()].sort((a, b) => a.date.localeCompare(b.date));
    if (!sorted.length) return null;
    const weights = sorted.map((m) => m.weight_kg);
    const first = weights[0];
    const last = weights[weights.length - 1];
    return {
      first,
      last,
      delta: Math.round((last - first) * 10) / 10,
      min: Math.min(...weights),
      max: Math.max(...weights),
      avg: weights.reduce((a, b) => a + b, 0) / weights.length,
    };
  });

  ngOnInit() {
    this.load();
  }

  async load() {
    this.loading.set(true);
    this.error.set(null);
    try {
      const [profile, page] = await Promise.all([
        firstValueFrom(this.api.getProfile()),
        firstValueFrom(this.api.listMeasurements({ limit: 500 })),
      ]);
      this.setProfile(profile);
      this.measurements.set(page.items);
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.loading.set(false);
    }
  }

  async saveProfile() {
    this.notice.set(null);
    this.error.set(null);
    if (this.height !== null && this.height <= 0) {
      this.error.set('Зріст має бути більший за 0.');
      return;
    }
    this.savingProfile.set(true);
    try {
      // an explicit null removes the value on the backend
      const profile = await firstValueFrom(
        this.api.patchProfile({ birth_date: this.birth || null, height_cm: this.height ?? null }),
      );
      this.setProfile(profile);
      this.notice.set('Дані збережено.');
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.savingProfile.set(false);
    }
  }

  async saveMeasurement() {
    this.notice.set(null);
    this.error.set(null);
    if (!this.mDate) {
      this.error.set('Вкажіть дату.');
      return;
    }
    if (this.mWeight === null || this.mWeight <= 0) {
      this.error.set('Вкажіть вагу більше 0.');
      return;
    }
    this.savingWeight.set(true);
    try {
      await firstValueFrom(this.api.putMeasurement(this.mDate, this.mWeight));
      this.mWeight = null;
      await this.load();
      this.notice.set('Вагу збережено.');
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.savingWeight.set(false);
    }
  }

  edit(m: BodyMeasurement) {
    this.mDate = m.date;
    this.mWeight = m.weight_kg;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async remove(m: BodyMeasurement) {
    if (!window.confirm(`Видалити запис ваги за ${formatDateShort(m.date)}?`)) return;
    this.error.set(null);
    this.notice.set(null);
    try {
      await firstValueFrom(this.api.deleteMeasurement(m.date));
      await this.load();
    } catch (e) {
      this.error.set(errorMessage(e));
    }
  }

  private setProfile(p: AthleteProfile) {
    this.profile.set(p);
    this.birth = p.birth_date ?? '';
    this.height = p.height_cm;
  }
}
