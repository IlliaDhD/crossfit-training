import { Component, computed, input } from '@angular/core';
import { formatNumber, parseIsoDate } from '../core/format';

export interface ChartPoint {
  date: string; // YYYY-MM-DD
  value: number;
  tip?: string; // tooltip text
}

const W = 640;
const H = 260;
const PAD = { l: 56, r: 16, t: 16, b: 34 };
const DAY = 86_400_000;

/** Small dependency-free SVG line chart for time series (X axis is proportional to the date). */
@Component({
  selector: 'app-line-chart',
  standalone: true,
  template: `
    <svg class="chart" [attr.viewBox]="'0 0 ' + W + ' ' + H" role="img" [attr.aria-label]="label()">
      @for (t of yTicks(); track t.y) {
        <line class="grid" [attr.x1]="pad.l" [attr.x2]="W - pad.r" [attr.y1]="t.y" [attr.y2]="t.y" />
        <text class="tick" text-anchor="end" [attr.x]="pad.l - 8" [attr.y]="t.y + 4">{{ t.text }}</text>
      }
      @for (t of xTicks(); track t.x) {
        <text class="tick" text-anchor="middle" [attr.x]="t.x" [attr.y]="H - 10">{{ t.text }}</text>
      }
      @if (dots().length > 1) {
        <path class="line" fill="none" [attr.d]="path()" />
      }
      @for (p of dots(); track $index) {
        <circle class="dot" r="4.5" [attr.cx]="p.x" [attr.cy]="p.y">
          <title>{{ p.tip }}</title>
        </circle>
      }
    </svg>
  `,
  styles: [
    `
      :host { display: block; }
      .chart { width: 100%; height: auto; display: block; }
      .grid { stroke: var(--x-border); stroke-width: 1; }
      .tick { fill: var(--x-muted); font-size: 11px; }
      .line { stroke: var(--x-accent); stroke-width: 2.5; stroke-linejoin: round; stroke-linecap: round; }
      .dot { fill: var(--x-surface); stroke: var(--x-accent); stroke-width: 2.5; }
      .dot:hover { fill: var(--x-accent); }
    `,
  ],
})
export class LineChartComponent {
  readonly points = input.required<ChartPoint[]>();
  readonly unit = input('');
  readonly decimals = input(1);
  readonly label = input('Графік');

  readonly W = W;
  readonly H = H;
  readonly pad = PAD;

  private readonly series = computed(() =>
    [...this.points()]
      .map((p) => ({ ...p, t: parseIsoDate(p.date).getTime() }))
      .sort((a, b) => a.t - b.t),
  );

  private readonly scale = computed(() => {
    const s = this.series();
    if (!s.length) return null;
    const t0 = s[0].t;
    const t1 = s[s.length - 1].t;
    let lo = Math.min(...s.map((p) => p.value));
    let hi = Math.max(...s.map((p) => p.value));
    if (lo === hi) {
      lo -= 1;
      hi += 1;
    } else {
      const margin = (hi - lo) * 0.12;
      lo -= margin;
      hi += margin;
    }
    const x = (t: number) =>
      t1 === t0 ? (PAD.l + W - PAD.r) / 2 : PAD.l + ((t - t0) / (t1 - t0)) * (W - PAD.l - PAD.r);
    const y = (v: number) => PAD.t + (1 - (v - lo) / (hi - lo)) * (H - PAD.t - PAD.b);
    return { t0, t1, lo, hi, x, y };
  });

  readonly dots = computed(() => {
    const sc = this.scale();
    if (!sc) return [];
    return this.series().map((p) => ({
      x: sc.x(p.t),
      y: sc.y(p.value),
      tip: p.tip ?? `${p.date}: ${formatNumber(p.value, this.decimals())} ${this.unit()}`.trim(),
    }));
  });

  readonly path = computed(() =>
    this.dots().map((d, i) => `${i ? 'L' : 'M'}${d.x.toFixed(1)},${d.y.toFixed(1)}`).join(' '),
  );

  readonly yTicks = computed(() => {
    const sc = this.scale();
    if (!sc) return [];
    return Array.from({ length: 5 }, (_, i) => {
      const v = sc.lo + ((sc.hi - sc.lo) * i) / 4;
      return { y: sc.y(v), text: formatNumber(v, this.decimals()) };
    });
  });

  readonly xTicks = computed(() => {
    const sc = this.scale();
    if (!sc) return [];
    const withYear = sc.t1 - sc.t0 > 200 * DAY;
    const n = sc.t1 === sc.t0 ? 1 : 5;
    return Array.from({ length: n }, (_, i) => {
      const t = n === 1 ? sc.t0 : sc.t0 + ((sc.t1 - sc.t0) * i) / (n - 1);
      return {
        x: sc.x(t),
        text: new Date(t).toLocaleDateString('uk-UA', {
          day: 'numeric', month: 'short', ...(withYear ? { year: '2-digit' as const } : {}),
        }),
      };
    });
  });
}
