import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { AuthService } from '../auth/auth.service';
import { SweetAlertService } from '../ui/sweet-alert.service';

@Component({
  selector: 'app-shell',
  imports: [FormsModule, RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './app-shell.component.html',
  styleUrls: ['./app-shell.component.scss', './app-shell-operations.scss'],
})
export class AppShellComponent {
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly alerts = inject(SweetAlertService);
  readonly menuOpen = signal(false);
  readonly profileOpen = signal(false);
  readonly search = signal('');
  readonly showGlobalSearch = signal(this.isOverviewUrl(this.router.url));
  readonly canCapture = computed(() => this.auth.hasRole('administrator', 'report_capturer'));
  readonly canViewReports = computed(() =>
    this.auth.hasRole('administrator', 'report_capturer', 'viewer'),
  );
  readonly initials = computed(() =>
    (this.auth.user()?.full_name ?? 'John Doe')
      .split(' ')
      .map((part) => part[0])
      .slice(0, 2)
      .join('')
      .toUpperCase(),
  );
  private searchTimer?: ReturnType<typeof setTimeout>;
  readonly roleLabel = computed(() =>
    (this.auth.user()?.role ?? 'administrator').replace('_', ' '),
  );

  constructor() {
    this.router.events
      .pipe(
        filter((event): event is NavigationEnd => event instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe((event) => this.showGlobalSearch.set(this.isOverviewUrl(event.urlAfterRedirects)));
  }

  closeMenu(): void {
    this.menuOpen.set(false);
  }
  toggleProfile(): void {
    this.profileOpen.update((open) => !open);
  }
  async logout(): Promise<void> {
    this.profileOpen.set(false);
    this.menuOpen.set(false);
    if (!(await this.alerts.confirm('Sign out?', 'You will need to sign in again to continue working.', 'Sign out', 'warning'))) return;
    this.auth.logout();
  }
  searchChanged(value: string): void {
    this.search.set(value);
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => this.runSearch(), 300);
  }

  runSearch(): void {
    void this.router.navigate(['/reports'], {
      queryParams: { q: this.search().trim() || null },
    });
  }

  private isOverviewUrl(url: string): boolean {
    return url.split(/[?#]/, 1)[0] === '/dashboard';
  }
}
