import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import Keycloak from 'keycloak-js';
import { routes } from './app.routes';
import { WelcomeComponent } from './welcome/welcome.component';

describe('Application routes', () => {
  let harness: RouterTestingHarness;
  let logout: jasmine.Spy;

  beforeEach(async () => {
    // Avoid starting the confetti animation in these navigation/UI tests.
    spyOn(window, 'matchMedia').and.returnValue({ matches: true } as MediaQueryList);
    logout = jasmine.createSpy('logout').and.resolveTo();

    await TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        {
          provide: Keycloak,
          useValue: {
            logout,
            tokenParsed: {
              name: 'Test Athlete',
              preferred_username: 'athlete',
              email: 'athlete@example.com',
              realm_access: { roles: ['athlete', 'offline_access', 'coach'] },
            },
          },
        },
      ],
    }).compileComponents();

    harness = await RouterTestingHarness.create();
    await harness.navigateByUrl('/', WelcomeComponent);
  });

  it('renders the signed-in user and only application roles on the home route', () => {
    const page = harness.routeNativeElement!;
    expect(page.querySelector('h1')?.textContent).toContain('Test Athlete');
    expect(page.textContent).toContain('athlete@example.com');
    expect(Array.from(page.querySelectorAll('.chip'), chip => chip.textContent?.trim()))
      .toEqual(['athlete', 'coach']);
  });

  it('logs out with a redirect to the application origin', () => {
    const button = harness.routeNativeElement!.querySelector<HTMLButtonElement>(
      '.actions button:not(.ghost)',
    )!;
    button.click();
    expect(logout).toHaveBeenCalledOnceWith({ redirectUri: window.location.origin });
  });

  it('redirects unknown URLs to the welcome page', async () => {
    await harness.navigateByUrl('/unknown-page', WelcomeComponent);
    expect(TestBed.inject(Router).url).toBe('/');
    expect(harness.routeNativeElement!.querySelector('h1')?.textContent)
      .toContain('Test Athlete');
  });
});
