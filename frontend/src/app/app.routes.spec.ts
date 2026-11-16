import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import Keycloak from 'keycloak-js';
import { routes } from './app.routes';
import { ExercisesComponent } from './exercises/exercises.component';

describe('Application routes', () => {
  let harness: RouterTestingHarness;
  let logout: jasmine.Spy;

  beforeEach(async () => {
    logout = jasmine.createSpy('logout').and.resolveTo();

    await TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: Keycloak,
          useValue: {
            logout,
            tokenParsed: {
              name: 'Test Athlete',
              preferred_username: 'athlete',
              realm_access: { roles: ['athlete', 'offline_access'] },
            },
          },
        },
      ],
    }).compileComponents();

    harness = await RouterTestingHarness.create();
  });

  it('opens the exercise catalog on the home route', async () => {
    await harness.navigateByUrl('/', ExercisesComponent);
    expect(TestBed.inject(Router).url).toBe('/exercises');
  });

  it('redirects unknown URLs to the exercise catalog', async () => {
    await harness.navigateByUrl('/unknown-page', ExercisesComponent);
    expect(TestBed.inject(Router).url).toBe('/exercises');
  });

  it('shows the signed-in user and logs out with a redirect to the application origin', async () => {
    await harness.navigateByUrl('/exercises', ExercisesComponent);
    const page: HTMLElement = harness.fixture.nativeElement;
    expect(page.querySelector('.user')?.textContent).toContain('athlete');
    page.querySelector<HTMLButtonElement>('.user button')!.click();
    expect(logout).toHaveBeenCalledOnceWith({ redirectUri: window.location.origin });
  });
});
