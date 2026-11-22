import { Routes } from '@angular/router';

export const PROJECTS_ROUTES: Routes = [
  {
    path: '',
    title: 'Projects · OPTICORE',
    loadComponent: () => import('./project-list/project-list').then((m) => m.ProjectList),
  },
  {
    path: ':id',
    title: 'Project · OPTICORE',
    loadComponent: () => import('./project-detail/project-detail').then((m) => m.ProjectDetail),
  },
];
