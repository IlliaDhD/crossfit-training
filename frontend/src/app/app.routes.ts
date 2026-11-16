import { Routes } from '@angular/router';
import { ShellComponent } from './layout/shell.component';

// TODO: add an auth guard with role checks (coach/athlete) for protected routes
export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'exercises' },
  {
    path: '',
    component: ShellComponent,
    children: [
      {
        path: 'exercises',
        loadComponent: () =>
          import('./exercises/exercises.component').then((m) => m.ExercisesComponent),
      },
      {
        path: 'builder',
        loadComponent: () => import('./builder/builder.component').then((m) => m.BuilderComponent),
      },
      {
        path: 'trainings',
        loadComponent: () =>
          import('./trainings/trainings.component').then((m) => m.TrainingsComponent),
      },
      {
        path: 'stats',
        loadComponent: () => import('./stats/stats.component').then((m) => m.StatsComponent),
      },
      {
        path: 'profile',
        loadComponent: () => import('./profile/profile.component').then((m) => m.ProfileComponent),
      },
    ],
  },
  { path: '**', redirectTo: 'exercises' },
];
