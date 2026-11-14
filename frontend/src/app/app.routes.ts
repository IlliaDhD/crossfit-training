import { Routes } from '@angular/router';
import { ShellComponent } from './layout/shell.component';
import { WelcomeComponent } from './welcome/welcome.component';

// TODO: add an auth guard with role checks (coach/athlete) for protected routes
export const routes: Routes = [
  { path: '', pathMatch: 'full', component: WelcomeComponent },
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
    ],
  },
  { path: '**', redirectTo: '' },
];
