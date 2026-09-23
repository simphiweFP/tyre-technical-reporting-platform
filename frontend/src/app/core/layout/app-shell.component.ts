import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../auth/auth.service';

@Component({
  selector: 'app-shell',
  imports: [FormsModule, RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './app-shell.component.html',
  styleUrls: ['./app-shell.component.scss', './app-shell-operations.scss'],
})
export class AppShellComponent {
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  readonly menuOpen = signal(false);
  readonly profileOpen = signal(false);
  readonly search = signal('');
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
  readonly roleLabel = computed(() =>
    (this.auth.user()?.role ?? 'administrator').replace('_', ' '),
  );
  closeMenu(): void {
    this.menuOpen.set(false);
  }
  toggleProfile(): void {
    this.profileOpen.update((open) => !open);
  }
  logout(): void {
    this.profileOpen.set(false);
    this.menuOpen.set(false);
    this.auth.logout();
  }
  runSearch(): void {
    void this.router.navigate(['/reports'], { queryParams: { q: this.search().trim() || null } });
  }
}
