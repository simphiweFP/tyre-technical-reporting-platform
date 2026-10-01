import { Routes } from '@angular/router';
import { authGuard, roleGuard } from './core/auth/auth.guard';
import { AppShellComponent } from './core/layout/app-shell.component';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./features/auth/login.component').then((m) => m.LoginComponent),
  },
  { path: 'register', redirectTo: 'login', pathMatch: 'full' },
  { path: 'forgot-password', redirectTo: 'login', pathMatch: 'full' },
  { path: 'reset-password', redirectTo: 'login', pathMatch: 'full' },
  { path: 'auth/callback', redirectTo: 'dashboard', pathMatch: 'full' },
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
        canActivate: [roleGuard('administrator', 'report_capturer', 'viewer')],
        loadComponent: () =>
          import('./features/reports/report-list.component').then((m) => m.ReportListComponent),
      },
      {
        path: 'reports/new',
        canActivate: [roleGuard('administrator', 'report_capturer')],
        loadComponent: () =>
          import('./features/report-capture/report-capture.component').then(
            (m) => m.ReportCaptureComponent,
          ),
      },
      {
        path: 'reports/:id',
        canActivate: [roleGuard('administrator', 'report_capturer', 'viewer')],
        loadComponent: () =>
          import('./features/reports/report-detail.component').then((m) => m.ReportDetailComponent),
      },
      {
        path: 'delivery-centre',
        canActivate: [roleGuard('administrator', 'report_capturer', 'viewer')],
        loadComponent: () =>
          import('./features/reports/delivery-centre.component').then(
            (m) => m.DeliveryCentreComponent,
          ),
      },
      {
        path: 'audit-viewer',
        canActivate: [roleGuard('administrator', 'report_capturer', 'viewer')],
        loadComponent: () =>
          import('./features/reports/report-viewer.component').then((m) => m.ReportViewerComponent),
      },
      {
        path: 'reports/:id/edit',
        canActivate: [roleGuard('administrator', 'report_capturer')],
        loadComponent: () =>
          import('./features/report-capture/report-capture.component').then(
            (m) => m.ReportCaptureComponent,
          ),
      },
      {
        path: 'admin/recipients',
        canActivate: [roleGuard('administrator')],
        loadComponent: () =>
          import('./features/admin/recipients.component').then((m) => m.RecipientsComponent),
      },
      {
        path: 'admin/branches',
        canActivate: [roleGuard('administrator')],
        loadComponent: () =>
          import('./features/admin/branches.component').then((m) => m.BranchesComponent),
      },
      {
        path: 'admin/settings',
        canActivate: [roleGuard('administrator')],
        loadComponent: () =>
          import('./features/admin/settings.component').then((m) => m.SettingsComponent),
      },
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
    ],
  },
  { path: '**', redirectTo: '' },
];
