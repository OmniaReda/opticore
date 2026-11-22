import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'projects' },
  {
    path: 'projects',
    title: 'Projects · OPTICORE',
    loadComponent: () =>
      import('./features/projects/project-list.component').then((m) => m.ProjectListComponent),
  },
  {
    path: 'projects/:id',
    title: 'Project · OPTICORE',
    loadComponent: () =>
      import('./features/projects/project-detail.component').then((m) => m.ProjectDetailComponent),
  },
  { path: '**', redirectTo: 'projects' },
];
