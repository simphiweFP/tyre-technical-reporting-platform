import { Routes } from '@angular/router';
import { authGuard, roleGuard } from './core/auth/auth.guard';
import { AppShellComponent } from './core/layout/app-shell.component';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./features/auth/login.component').then((m) => m.LoginComponent),
  },
  {
    path: '',
    component: AppShellComponent,
    canActivate: [authGuard],
    children: [
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent),
      },
      {
        path: 'reports',
        loadComponent: () =>
          import('./features/reports/report-list.component').then((m) => m.ReportListComponent),
      },
      {
        path: 'reports/new',
        loadComponent: () =>
          import('./features/report-capture/report-capture.component').then(
            (m) => m.ReportCaptureComponent,
          ),
      },
      {
        path: 'reports/:id/edit',
        loadComponent: () =>
          import('./features/report-capture/report-capture.component').then(
            (m) => m.ReportCaptureComponent,
          ),
      },
      {
        path: 'admin/users',
        canActivate: [roleGuard('administrator')],
        loadComponent: () =>
          import('./features/admin/users.component').then((m) => m.UsersComponent),
      },
      {
        path: 'admin/recipients',
        canActivate: [roleGuard('administrator')],
        loadComponent: () =>
          import('./features/admin/recipients.component').then((m) => m.RecipientsComponent),
      },
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
    ],
  },
  { path: '**', redirectTo: '' },
];
