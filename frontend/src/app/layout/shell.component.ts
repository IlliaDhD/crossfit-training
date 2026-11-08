import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import Keycloak from 'keycloak-js';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <header class="bar">
      <a class="brand" routerLink="/exercises">CROSSFIT</a>
      <nav class="tabs" aria-label="Розділи">
        <a routerLink="/exercises" routerLinkActive="active">Каталог вправ</a>
        <a routerLink="/builder" routerLinkActive="active">Конструктор</a>
        <a routerLink="/trainings" routerLinkActive="active">Тренування</a>
      </nav>
      <div class="user">
        <a class="x-muted home" routerLink="/">{{ username }}</a>
        <button type="button" class="x-btn small ghost" (click)="logout()">Вийти</button>
      </div>
    </header>
    <main class="content"><router-outlet /></main>
  `,
  styles: [
    `
      :host {
        display: block;
        min-height: 100vh;
        background: var(--x-bg);
        color: var(--x-text);
        font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
      }
      .bar {
        position: sticky;
        top: 0;
        z-index: 10;
        display: flex;
        align-items: center;
        gap: 1.5rem;
        padding: 0.7rem 1.5rem;
        background: var(--x-bar);
        backdrop-filter: blur(8px);
        border-bottom: 1px solid var(--x-border);
      }
      .brand {
        font-weight: 800;
        letter-spacing: 0.18em;
        color: var(--x-text);
        text-decoration: none;
      }
      .tabs { display: flex; gap: 0.3rem; flex: 1; }
      .tabs a {
        padding: 0.5rem 1rem;
        border-radius: 10px;
        color: var(--x-muted);
        text-decoration: none;
        font-weight: 600;
      }
      .tabs a:hover { color: var(--x-text); }
      .tabs a.active { color: #fff; background: var(--x-accent); }
      .user { display: flex; align-items: center; gap: 0.8rem; }
      .home { text-decoration: none; }
      .content { max-width: 1200px; margin: 0 auto; padding: 1.5rem; }
      @media (max-width: 700px) {
        .bar { flex-wrap: wrap; gap: 0.6rem; padding: 0.6rem 1rem; }
        .tabs { order: 3; width: 100%; overflow-x: auto; }
        .tabs a { white-space: nowrap; }
        .content { padding: 1rem; }
      }
    `,
  ],
})
export class ShellComponent {
  private keycloak = inject(Keycloak);
  username: string = this.keycloak.tokenParsed?.['preferred_username'] ?? '';

  logout() {
    this.keycloak.logout({ redirectUri: window.location.origin });
  }
}
