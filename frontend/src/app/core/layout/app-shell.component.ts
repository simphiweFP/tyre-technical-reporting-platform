import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../auth/auth.service';
@Component({
  selector: 'app-shell',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  template: `
    <div class="app-frame">
      <aside class="sidebar" [class.open]="menuOpen()">
        <div class="brand">
          <div class="brand-mark">RT</div>
          <div><strong>Royal Tyres</strong><span>Technical Reports</span></div>
          <button
            class="icon-button close-menu"
            (click)="menuOpen.set(false)"
            aria-label="Close navigation"
          >
            ×
          </button>
        </div>
        <nav aria-label="Primary navigation">
          <a routerLink="/dashboard" routerLinkActive="active" (click)="closeMenu()"
            ><span>⌂</span>Overview</a
          >
          @if (canViewReports()) {
            <a routerLink="/reports" routerLinkActive="active" (click)="closeMenu()"
              ><span>▤</span>Reports</a
            >
          }
          @if (canCapture()) {
            <a routerLink="/reports/new" routerLinkActive="active" (click)="closeMenu()"
              ><span>＋</span>New report</a
            >
          }
          @if (auth.hasRole('administrator')) {
            <p class="nav-label">Administration</p>
            <a routerLink="/admin/users" routerLinkActive="active" (click)="closeMenu()"
              ><span>♙</span>Users</a
            ><a routerLink="/admin/recipients" routerLinkActive="active" (click)="closeMenu()"
              ><span>✉</span>Recipients</a
            >
          }
        </nav>
        <div class="sidebar-footer">
          <div class="user-avatar">{{ initials() }}</div>
          <div class="user-summary">
            <strong>{{ auth.user()?.full_name }}</strong
            ><span>{{ roleLabel() }}</span>
          </div>
          <button
            class="icon-button"
            (click)="auth.logout()"
            title="Sign out"
            aria-label="Sign out"
          >
            ↪
          </button>
        </div>
      </aside>
      @if (menuOpen()) {
        <button class="scrim" aria-label="Close navigation" (click)="menuOpen.set(false)"></button>
      }
      <main class="main-panel">
        <header class="mobile-header">
          <button class="icon-button" (click)="menuOpen.set(true)" aria-label="Open navigation">
            ☰
          </button>
          <div class="mobile-brand">
            <span class="brand-mark small">RT</span><strong>Technical Reports</strong>
          </div>
          <div class="user-avatar small">{{ initials() }}</div>
        </header>
        <router-outlet />
      </main>
    </div>
  `,
  styleUrl: './app-shell.component.scss',
})
export class AppShellComponent {
  readonly auth = inject(AuthService);
  readonly menuOpen = signal(false);
  readonly canCapture = computed(() => this.auth.hasRole('administrator', 'report_capturer'));
  readonly canViewReports = computed(() =>
    this.auth.hasRole('administrator', 'report_capturer', 'viewer'),
  );
  readonly initials = computed(() =>
    (this.auth.user()?.full_name ?? 'User')
      .split(' ')
      .map((part) => part[0])
      .slice(0, 2)
      .join('')
      .toUpperCase(),
  );
  readonly roleLabel = computed(() => (this.auth.user()?.role ?? '').replace('_', ' '));
  closeMenu(): void {
    this.menuOpen.set(false);
  }
}
