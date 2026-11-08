import { Component, computed, input, output } from '@angular/core';
import {
  FORMAT_LABEL, KIND_LABEL, formatDateLong, formatDuration, formatSet, plural, tonnage,
} from '../core/format';
import { ComplexMarker, SetOut, Training } from '../core/models';

interface Group {
  marker: ComplexMarker | null;
  items: SetOut[];
}

@Component({
  selector: 'app-training-detail',
  standalone: true,
  template: `
    <article class="x-card detail">
      <header class="top">
        <div>
          <h3>{{ training().title }}</h3>
          <p class="x-muted date">{{ dateLong() }}</p>
        </div>
        <button type="button" class="x-btn small danger" (click)="remove.emit()">Видалити</button>
      </header>

      @if (training().comment) {
        <p class="comment">{{ training().comment }}</p>
      }

      <div class="stats">
        <div><b>{{ view().sections.length }}</b><span>{{ sectionsWord() }}</span></div>
        <div><b>{{ view().sets }}</b><span>{{ setsWord() }}</span></div>
        <div><b>{{ view().tonnage }}</b><span>кг тоннаж</span></div>
      </div>

      @for (s of view().sections; track $index) {
        <section class="sec">
          <h4>
            <span class="x-chip kind">{{ s.kindLabel }}</span>
            <span class="x-muted meta">{{ s.meta }}</span>
          </h4>
          @if (s.comment) {
            <p class="x-muted note">{{ s.comment }}</p>
          }
          @for (g of s.groups; track $index) {
            @if (g.marker) {
              <div class="cx">Комплекс «{{ g.marker.name }}» · раунд {{ g.marker.round }}</div>
            }
            <ul class="sets" [class.nested]="g.marker">
              @for (it of g.items; track $index) {
                <li>
                  <span class="x-badge" [attr.data-m]="it.type">{{ it.type }}</span>
                  <span class="nm">{{ it.exercise.name }}</span>
                  <span class="val">{{ format(it) }}</span>
                  @if (it.comment) {
                    <em class="x-muted">{{ it.comment }}</em>
                  }
                </li>
              }
            </ul>
          }
        </section>
      }
    </article>
  `,
  styles: [
    `
      .top { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; }
      h3 { margin: 0; font-size: 1.3rem; }
      .date { margin: 0.2rem 0 0.8rem; text-transform: capitalize; }
      .comment { margin: 0 0 1rem; padding: 0.6rem 0.8rem; border-radius: 10px; background: var(--x-overlay); }
      .stats { display: flex; gap: 0.6rem; margin-bottom: 1rem; }
      .stats div {
        flex: 1; text-align: center; padding: 0.6rem; border-radius: 12px;
        background: var(--x-overlay); display: flex; flex-direction: column;
      }
      .stats b { font-size: 1.4rem; }
      .stats span { font-size: 0.75rem; color: var(--x-muted); }
      .sec { padding-top: 0.9rem; border-top: 1px solid var(--x-border); }
      h4 { margin: 0 0 0.5rem; display: flex; gap: 0.6rem; align-items: center; flex-wrap: wrap; }
      .kind { background: var(--x-accent); color: #fff; font-size: 0.8rem; }
      .meta { font-weight: 400; font-size: 0.85rem; }
      .note { margin: 0 0 0.5rem; font-size: 0.85rem; }
      .cx { margin: 0.6rem 0 0.2rem; font-size: 0.85rem; color: var(--x-warn); }
      .sets { list-style: none; margin: 0 0 0.6rem; padding: 0; }
      .sets.nested { margin-left: 0.8rem; padding-left: 0.8rem; border-left: 2px solid var(--x-warn); }
      .sets li { display: flex; flex-wrap: wrap; gap: 0.2rem 0.7rem; align-items: baseline; padding: 0.35rem 0; }
      .nm { font-weight: 600; }
      .val { color: var(--x-ok); margin-left: auto; }
    `,
  ],
})
export class TrainingDetailComponent {
  readonly training = input.required<Training>();
  readonly remove = output<void>();

  readonly format = formatSet;
  readonly dateLong = computed(() => formatDateLong(this.training().date));

  readonly view = computed(() => {
    const t = this.training();
    let sets = 0;
    const sections = t.sections.map((s) => {
      sets += s.items.length;
      const meta = [
        FORMAT_LABEL[s.format],
        s.rounds ? `${s.rounds} ${plural(s.rounds, ['раунд', 'раунди', 'раундів'])}` : '',
        s.time_cap ? `time cap ${formatDuration(s.time_cap)}` : '',
      ].filter(Boolean).join(' · ');
      return { kindLabel: KIND_LABEL[s.kind], meta, comment: s.comment, groups: this.group(s.items) };
    });
    return { sections, sets, tonnage: tonnage(t) };
  });

  readonly sectionsWord = computed(() =>
    plural(this.view().sections.length, ['секція', 'секції', 'секцій']),
  );
  readonly setsWord = computed(() => plural(this.view().sets, ['підхід', 'підходи', 'підходів']));

  /** Consecutive sets that came from the same complex round are shown as one block. */
  private group(items: SetOut[]): Group[] {
    const groups: Group[] = [];
    for (const it of items) {
      const last = groups[groups.length - 1];
      const same =
        last &&
        last.marker &&
        it.complex &&
        last.marker.id === it.complex.id &&
        last.marker.round === it.complex.round;
      if (same || (last && !last.marker && !it.complex)) {
        last.items.push(it);
      } else {
        groups.push({ marker: it.complex ?? null, items: [it] });
      }
    }
    return groups;
  }
}
