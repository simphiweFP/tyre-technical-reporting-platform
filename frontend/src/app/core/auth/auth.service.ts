import { HttpClient } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { Router } from '@angular/router';
import { finalize, Observable, shareReplay, tap } from 'rxjs';
import { firstValueFrom } from 'rxjs';
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
  private refreshInFlight: Observable<TokenResponse> | null = null;
  readonly user = computed(() => this.session()?.user ?? null);
  readonly isAuthenticated = computed(() => !!this.session()?.accessToken);
  readonly accessToken = computed(() => this.session()?.accessToken ?? null);
  readonly refreshToken = computed(() => this.session()?.refreshToken ?? null);
  login(email: string, password: string): Observable<TokenResponse> {
    return this.http
      .post<TokenResponse>(`${environment.apiUrl}/auth/login`, { email, password })
      .pipe(tap((response) => this.storeSession(response)));
  }
  register(fullName: string, email: string, password: string): Observable<TokenResponse> {
    return this.http
      .post<TokenResponse>(`${environment.apiUrl}/auth/register`, {
        full_name: fullName,
        email,
        password,
      })
      .pipe(tap((response) => this.storeSession(response)));
  }
  microsoftLoginUrl(): string {
    return `${environment.apiUrl}/auth/microsoft/login`;
  }
  async completeMicrosoft(accessToken: string, refreshToken: string): Promise<void> {
    const user = await firstValueFrom(
      this.http.get<CurrentUser>(`${environment.apiUrl}/auth/me`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      }),
    );
    this.storeSession({
      access_token: accessToken,
      refresh_token: refreshToken,
      token_type: 'bearer',
      user,
    });
  }
  forgotPassword(email: string): Observable<unknown> {
    return this.http.post(`${environment.apiUrl}/auth/forgot-password`, { email });
  }
  resetPassword(token: string, newPassword: string): Observable<void> {
    return this.http.post<void>(`${environment.apiUrl}/auth/reset-password`, {
      token,
      new_password: newPassword,
    });
  }
  refreshSession(): Observable<TokenResponse> {
    if (this.refreshInFlight) return this.refreshInFlight;
    this.refreshInFlight = this.http
      .post<TokenResponse>(`${environment.apiUrl}/auth/refresh`, {
        refresh_token: this.refreshToken(),
      })
      .pipe(
        tap((response) => this.storeSession(response)),
        finalize(() => (this.refreshInFlight = null)),
        shareReplay(1),
      );
    return this.refreshInFlight;
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
    this.expireSession();
  }
  expireSession(): void {
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
