import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-forgot-password',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <main class="auth-page">
      <header class="auth-topbar">
        <a class="auth-brand" routerLink="/login"><img src="/royal-tyres-app-logo.png" alt="Royal Tyres" /></a>
        <span>Technical Reporting Platform</span>
      </header>

      <section class="auth-shell">
        <section class="product-panel">
          <div class="product-copy">
            <p class="product-kicker">Secure access</p>
            <h1>Get back to your reports securely.</h1>
            <p class="product-intro">
              Password recovery is part of the same protected staff workflow. Your reports and
              captured data remain unchanged.
            </p>
            <div class="workflow-strip">
              <article><span>01</span><div><strong>Request</strong><small>Enter your account email</small></div></article>
              <article><span>02</span><div><strong>Verify</strong><small>Open the secure reset link</small></div></article>
              <article><span>03</span><div><strong>Return</strong><small>Continue your reports</small></div></article>
            </div>
          </div>
        </section>

        <section class="form-panel">
          <div class="login-card">
            <div class="form-brand">
              <img src="/royal-tyres-app-logo.png" alt="Royal Tyres" />
              <span>Account recovery</span>
            </div>
            <p class="eyebrow">Account recovery</p>
            <h2>Reset password</h2>
            <p class="subtext">Enter your account email and we’ll send you a secure reset link.</p>

            <form [formGroup]="form" (ngSubmit)="submit()">
              <div class="field">
                <label>Email address</label>
                <input type="email" formControlName="email" placeholder="name@royaltyres.co.za" />
              </div>
              <button class="button primary" type="submit" [disabled]="form.invalid">Send reset link</button>
            </form>

            @if (message()) {
              <div class="login-error standalone-message">{{ message() }}</div>
            }

            <p class="support"><a routerLink="/login">← Back to sign in</a></p>
          </div>
        </section>
      </section>
    </main>
  `,
  styleUrl: './login.component.scss',
})
export class ForgotPasswordComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  readonly message = signal('');
  readonly form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
  });

  submit(): void {
    this.auth.forgotPassword(this.form.controls.email.value).subscribe({
      next: () => this.message.set('If the account exists, reset instructions have been sent.'),
      error: () => this.message.set('The request could not be completed. Try again.'),
    });
  }
}

@Component({
  selector: 'app-reset-password',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <main class="auth-page">
      <header class="auth-topbar">
        <a class="auth-brand" routerLink="/login"><img src="/royal-tyres-app-logo.png" alt="Royal Tyres" /></a>
        <span>Technical Reporting Platform</span>
      </header>

      <section class="auth-shell">
        <section class="product-panel">
          <div class="product-copy">
            <p class="product-kicker">Secure access</p>
            <h1>Choose a new password and continue.</h1>
            <p class="product-intro">
              Once updated, you can return directly to the same Royal Tyres reporting workspace.
            </p>
            <div class="product-preview compact-preview">
              <div class="preview-head">
                <div><small>ACCOUNT SECURITY</small><strong>Protected staff access</strong></div>
                <span>Secure</span>
              </div>
              <p>Your report data is not changed during password recovery.</p>
            </div>
          </div>
        </section>

        <section class="form-panel">
          <div class="login-card">
            <div class="form-brand">
              <img src="/royal-tyres-app-logo.png" alt="Royal Tyres" />
              <span>Account recovery</span>
            </div>
            <p class="eyebrow">Account recovery</p>
            <h2>Choose a new password</h2>
            <p class="subtext">Use at least 12 characters for your new password.</p>

            <form [formGroup]="form" (ngSubmit)="submit()">
              <div class="field">
                <label>New password</label>
                <input type="password" formControlName="password" autocomplete="new-password" placeholder="Create a new password" />
              </div>
              <button class="button primary" type="submit" [disabled]="form.invalid">Update password</button>
            </form>

            @if (message()) {
              <div class="login-error standalone-message">{{ message() }}</div>
            }
          </div>
        </section>
      </section>
    </main>
  `,
  styleUrl: './login.component.scss',
})
export class ResetPasswordComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly message = signal('');
  readonly form = this.fb.nonNullable.group({
    password: ['', [Validators.required, Validators.minLength(12)]],
  });

  submit(): void {
    const token = this.route.snapshot.queryParamMap.get('token') ?? '';
    this.auth.resetPassword(token, this.form.controls.password.value).subscribe({
      next: () => void this.router.navigate(['/login']),
      error: (response) => this.message.set(response.error?.detail ?? 'Reset link is invalid.'),
    });
  }
}
