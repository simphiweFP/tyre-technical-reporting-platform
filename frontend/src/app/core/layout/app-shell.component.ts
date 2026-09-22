import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../auth/auth.service';

@Component({
  selector: 'app-shell',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './app-shell.component.html',
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
}
