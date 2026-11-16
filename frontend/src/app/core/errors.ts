import { HttpErrorResponse } from '@angular/common/http';
import { API_URL } from './api.config';

/** Turns an HTTP error from the API into a readable message. */
export function errorMessage(e: unknown): string {
  if (!(e instanceof HttpErrorResponse)) return 'Невідома помилка';
  if (e.status === 0) return `Немає зв'язку з сервером. Перевірте, чи запущений бекенд (${API_URL}).`;
  if (e.status === 401) return 'Сесія закінчилась. Оновіть сторінку, щоб увійти знову.';
  if (e.status === 403) return 'Недостатньо прав для цієї дії.';
  if (e.status === 409) return 'Такий запис уже існує. Змініть назву або ідентифікатор (slug).';
  const detail = e.error?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) =>
        [d.loc?.slice(1).join('.'), d.msg].filter(Boolean).join(': '),
      )
      .join('; ');
  }
  return `Помилка сервера (${e.status})`;
}
