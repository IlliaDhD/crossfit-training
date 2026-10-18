import {
  AfterViewInit,
  Component,
  ElementRef,
  NgZone,
  OnDestroy,
  ViewChild,
  inject,
} from '@angular/core';
import Keycloak from 'keycloak-js';

interface Piece {
  x: number;
  y: number;
  w: number;
  h: number;
  vx: number;
  vy: number;
  rot: number;
  vr: number;
  color: string;
}

const COLORS = ['#ff4d6d', '#ffd166', '#06d6a0', '#4cc9f0', '#b388ff', '#ff9f1c', '#ffffff'];

@Component({
  selector: 'app-welcome',
  standalone: true,
  template: `
    <canvas #confetti class="confetti"></canvas>

    <main class="page">
      <section class="card">
        <div class="emoji">🎉</div>
        <h1>Вітаємо, {{ name }}!</h1>
        <p class="subtitle">Ви успішно увійшли в систему</p>

        <div class="chips">
          @for (role of roles; track role) {
            <span class="chip">{{ role }}</span>
          }
        </div>

        <ul class="info">
          <li><span>Логін</span><b>{{ username }}</b></li>
          <li><span>Email</span><b>{{ email }}</b></li>
        </ul>

        <div class="actions">
          <button class="ghost" (click)="burst()">🎊 Ще конфеті</button>
          <button (click)="logout()">Вийти</button>
        </div>
      </section>
    </main>
  `,
  styles: [
    `
      :host {
        display: block;
        min-height: 100vh;
        font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
        background: linear-gradient(135deg, #1b1464, #5b2a86, #c2185b, #ff7e5f);
        background-size: 300% 300%;
        animation: bg 14s ease infinite;
        color: #fff;
      }
      @keyframes bg {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
      }
      .confetti {
        position: fixed;
        inset: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: 1;
      }
      .page {
        position: relative;
        z-index: 2;
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 1.5rem;
      }
      .card {
        width: 100%;
        max-width: 520px;
        padding: 2.5rem 2rem;
        text-align: center;
        background: rgba(255, 255, 255, 0.14);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 24px;
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
      }
      .emoji { font-size: 3.5rem; animation: pop 1.2s ease infinite; }
      @keyframes pop {
        0%, 100% { transform: scale(1) rotate(0); }
        50% { transform: scale(1.15) rotate(-8deg); }
      }
      h1 { margin: 0.5rem 0 0.25rem; font-size: 2rem; }
      .subtitle { margin: 0 0 1rem; opacity: 0.9; font-size: 1.1rem; }
      .chips { display: flex; gap: 0.5rem; justify-content: center; margin-bottom: 1rem; }
      .chip {
        padding: 0.2rem 0.8rem;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.25);
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
      }
      .info { list-style: none; padding: 0; margin: 0 0 1rem; text-align: left; }
      .info li {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        padding: 0.55rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.2);
      }
      .info span { opacity: 0.8; }
      .actions { display: flex; gap: 0.75rem; justify-content: center; }
      button {
        cursor: pointer;
        border: none;
        border-radius: 12px;
        padding: 0.7rem 1.4rem;
        font-size: 1rem;
        font-weight: 600;
        color: #1b1464;
        background: #fff;
        transition: transform 0.15s;
      }
      button:hover { transform: translateY(-2px); }
      button.ghost { background: rgba(255, 255, 255, 0.2); color: #fff; }
      @media (prefers-reduced-motion: reduce) {
        :host, .emoji { animation: none; }
      }
    `,
  ],
})
export class WelcomeComponent implements AfterViewInit, OnDestroy {
  keycloak = inject(Keycloak);
  private zone = inject(NgZone);

  @ViewChild('confetti', { static: true }) canvasRef!: ElementRef<HTMLCanvasElement>;

  private claims = this.keycloak.tokenParsed ?? {};
  name: string = this.claims['name'] ?? this.claims['preferred_username'];
  username: string = this.claims['preferred_username'];
  email: string = this.claims['email'];
  roles: string[] = (this.claims['realm_access']?.roles ?? []).filter(
    (r: string) => ['coach', 'athlete'].includes(r),
  );

  private raf = 0;
  private pieces: Piece[] = [];
  private ctx!: CanvasRenderingContext2D;
  private reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  ngAfterViewInit() {
    if (this.reducedMotion) return;

    const canvas = this.canvasRef.nativeElement;
    this.ctx = canvas.getContext('2d')!;
    this.resize();
    window.addEventListener('resize', this.resize);
    this.burst();
    this.zone.runOutsideAngular(() => this.loop());
  }

  ngOnDestroy() {
    cancelAnimationFrame(this.raf);
    window.removeEventListener('resize', this.resize);
  }

  burst() {
    if (this.reducedMotion) return;
    const w = this.canvasRef.nativeElement.width;
    for (let i = 0; i < 160; i++) this.pieces.push(this.piece(Math.random() * w, -20 - Math.random() * 300));
  }

  logout() {
    this.keycloak.logout({ redirectUri: window.location.origin });
  }

  private piece(x: number, y: number): Piece {
    return {
      x,
      y,
      w: 6 + Math.random() * 8,
      h: 10 + Math.random() * 10,
      vx: -1.5 + Math.random() * 3,
      vy: 1.5 + Math.random() * 3,
      rot: Math.random() * Math.PI * 2,
      vr: -0.15 + Math.random() * 0.3,
      color: COLORS[Math.floor(Math.random() * COLORS.length)],
    };
  }

  private resize = () => {
    const c = this.canvasRef.nativeElement;
    c.width = window.innerWidth;
    c.height = window.innerHeight;
  };

  private loop = () => {
    const c = this.canvasRef.nativeElement;
    this.ctx.clearRect(0, 0, c.width, c.height);

    // постійний тонкий потік конфеті
    if (this.pieces.length < 120 && Math.random() < 0.6) {
      this.pieces.push(this.piece(Math.random() * c.width, -20));
    }

    for (const p of this.pieces) {
      p.x += p.vx + Math.sin(p.y / 40);
      p.y += p.vy;
      p.rot += p.vr;
      this.ctx.save();
      this.ctx.translate(p.x, p.y);
      this.ctx.rotate(p.rot);
      this.ctx.fillStyle = p.color;
      this.ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
      this.ctx.restore();
    }

    this.pieces = this.pieces.filter((p) => p.y < c.height + 30);
    this.raf = requestAnimationFrame(this.loop);
  };
}
