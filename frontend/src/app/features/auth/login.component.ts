import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <main class="auth-page">
      <header class="auth-topbar">
        <a class="auth-brand" routerLink="/login">
          <img src="/royal-tyres-app-logo.png" alt="Royal Tyres" />
        </a>
        <span>Technical Reporting Platform</span>
      </header>

      <section class="auth-shell">
        <section class="product-panel">
          <div class="product-copy">
            <p class="product-kicker">Peak Performance Tyres · Royal Tyres</p>
            <h1>Technical reporting, built for the workshop.</h1>
            <p class="product-intro">
              Capture inspections, manage tyre claims and deliver professional reports from one
              connected workspace.
            </p>

            <div class="workflow-experience">
              <div class="journey-rail" aria-label="Technical reporting workflow">
                <article class="journey-step complete">
                  <span class="step-dot">01</span>
                  <div><strong>Capture</strong><small>Claim details</small></div>
                </article>
                <article class="journey-step current">
                  <span class="step-dot">02</span>
                  <div><strong>Inspect</strong><small>Tyre data + photos</small></div>
                </article>
                <article class="journey-step">
                  <span class="step-dot">03</span>
                  <div><strong>Deliver</strong><small>Report + email</small></div>
                </article>
              </div>

              <div class="claim-snapshot">
                <div class="snapshot-main">
                  <div class="snapshot-title">
                    <span class="snapshot-icon">TR</span>
                    <div>
                      <small>ACTIVE TECHNICAL CLAIM</small>
                      <strong>TR-2026-4F1501</strong>
                    </div>
                  </div>
                  <span class="snapshot-status">Draft</span>
                </div>

                <div class="snapshot-meta">
                  <span><b>Phoenix</b><small>Branch</small></span>
                  <span><b>Bridgestone</b><small>Tyre</small></span>
                  <span><b>12 / 16</b><small>Photos captured</small></span>
                </div>

                <div class="snapshot-footer">
                  <div>
                    <span class="snapshot-progress"><i></i></span>
                    <small>Inspection in progress</small>
                  </div>
                  <strong>Continue capture →</strong>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="form-panel">
          <div class="login-card">
            <div class="form-brand">
              <img src="/royal-tyres-app-logo.png" alt="Royal Tyres" />
              <span>Staff portal</span>
            </div>
            <p class="eyebrow">Staff portal</p>
            <h2>Welcome back</h2>
            <p class="subtext">Sign in to the Royal Tyres technical reporting platform.</p>

            <a class="button microsoft" [href]="auth.microsoftLoginUrl()">
              <span class="microsoft-mark">M</span>
              Continue with Microsoft / Outlook
            </a>

            <div class="divider"><span>or use your account</span></div>

            <form [formGroup]="form" (ngSubmit)="submit()">
              <div class="field">
                <label for="email">Email address</label>
                <input
                  id="email"
                  type="email"
                  formControlName="email"
                  autocomplete="username"
                  placeholder="name@royaltyres.co.za"
                />
              </div>
              <div class="field">
                <label for="password">
                  Password
                  <a routerLink="/forgot-password">Forgot password?</a>
                </label>
                <input
                  id="password"
                  type="password"
                  formControlName="password"
                  autocomplete="current-password"
                  placeholder="Enter your password"
                />
              </div>

              @if (error()) {
                <div class="login-error">{{ error() }}</div>
              }

              <button class="button primary" type="submit" [disabled]="form.invalid || loading()">
                {{ loading() ? 'Signing in…' : 'Sign in securely' }}
              </button>
            </form>

            <p class="support">New here? <a routerLink="/register">Create a new account</a></p>
          </div>
        </section>
      </section>
    </main>
  `,
  styleUrl: './login.component.scss',
})
export class LoginComponent {
  private readonly fb = inject(FormBuilder);
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]],
  });

  submit(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set('');
    this.auth.login(this.form.controls.email.value, this.form.controls.password.value).subscribe({
      next: () => void this.router.navigate(['/dashboard']),
      error: (response) => {
        this.loading.set(false);
        this.error.set(
          response.status === 0
            ? 'Cannot reach the API. Check that the backend is running.'
            : 'Email or password is incorrect.',
        );
      },
    });
  }
}
