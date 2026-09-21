import { HttpClient } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { CurrentUser, TokenResponse, UserRole } from '../../shared/models/auth.models';
const SESSION_KEY = 'royal-tyres.session';
interface SessionState {
  accessToken: string;
  refreshToken: string;
  user: CurrentUser;
}
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly session = signal<SessionState | null>(this.readSession());
  readonly user = computed(() => this.session()?.user ?? null);
  readonly isAuthenticated = computed(() => !!this.session()?.accessToken);
  readonly accessToken = computed(() => this.session()?.accessToken ?? null);
  login(email: string, password: string): Observable<TokenResponse> {
    return this.http
      .post<TokenResponse>(`${environment.apiUrl}/auth/login`, { email, password })
      .pipe(tap((response) => this.storeSession(response)));
  }
  hasRole(...roles: UserRole[]): boolean {
    const role = this.user()?.role;
    return !!role && roles.includes(role);
  }
  logout(): void {
    const refreshToken = this.session()?.refreshToken;
    if (refreshToken)
      this.http
        .post(`${environment.apiUrl}/auth/logout`, { refresh_token: refreshToken })
        .subscribe({ error: () => undefined });
    localStorage.removeItem(SESSION_KEY);
    this.session.set(null);
    void this.router.navigate(['/login']);
  }
  private storeSession(response: TokenResponse): void {
    const value = {
      accessToken: response.access_token,
      refreshToken: response.refresh_token,
      user: response.user,
    };
    localStorage.setItem(SESSION_KEY, JSON.stringify(value));
    this.session.set(value);
  }
  private readSession(): SessionState | null {
    try {
      const value = localStorage.getItem(SESSION_KEY);
      return value ? (JSON.parse(value) as SessionState) : null;
    } catch {
      localStorage.removeItem(SESSION_KEY);
      return null;
    }
  }
}
