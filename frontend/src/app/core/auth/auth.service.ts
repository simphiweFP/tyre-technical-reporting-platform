import { HttpClient } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { CurrentUser, UserRole } from '../../shared/models/auth.models';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly currentUser = signal<CurrentUser | null>(null);
  private sessionCheck: Promise<boolean> | null = null;

  readonly user = computed(() => this.currentUser());
  readonly isAuthenticated = computed(() => this.currentUser() !== null);

  companyLoginUrl(): string {
    return `${environment.apiUrl}/auth/company-login`;
  }

  async ensureSession(force = false): Promise<boolean> {
    if (!force && this.currentUser()) return true;
    if (!force && this.sessionCheck) return this.sessionCheck;

    this.sessionCheck = firstValueFrom(
      this.http.get<CurrentUser>(`${environment.apiUrl}/auth/me`),
    )
      .then((user) => {
        this.currentUser.set(user);
        return true;
      })
      .catch(() => {
        this.currentUser.set(null);
        return false;
      })
      .finally(() => {
        this.sessionCheck = null;
      });

    return this.sessionCheck;
  }

  hasRole(...roles: UserRole[]): boolean {
    const role = this.currentUser()?.role;
    return !!role && roles.includes(role);
  }

  async logout(): Promise<void> {
    try {
      await firstValueFrom(
        this.http.post<void>(`${environment.apiUrl}/auth/company-logout`, {}),
      );
    } finally {
      this.currentUser.set(null);
      await this.router.navigate(['/login']);
    }
  }

  expireSession(): void {
    this.currentUser.set(null);
    void this.router.navigate(['/login']);
  }
}
