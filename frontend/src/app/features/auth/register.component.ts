import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-register',
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
            <p class="product-kicker">Peak Performance Tyres · Royal Tyres</p>
            <h1>Join the reporting workflow.</h1>
            <p class="product-intro">
              One secure account gives your team access to guided capture, technical claim history
              and report delivery.
            </p>

            <div class="workflow-strip">
              <article><span>01</span><div><strong>Register</strong><small>Create your staff access</small></div></article>
              <article><span>02</span><div><strong>Assigned</strong><small>Admin sets your role</small></div></article>
              <article><span>03</span><div><strong>Report</strong><small>Start capturing claims</small></div></article>
            </div>

            <div class="product-preview compact-preview">
              <div class="preview-head">
                <div><small>ACCESS FLOW</small><strong>Secure staff onboarding</strong></div>
                <span>Pending</span>
              </div>
              <p>
                New accounts stay protected until an administrator assigns the correct branch and
                reporting permission.
              </p>
            </div>
          </div>
        </section>

        <section class="form-panel">
          <div class="login-card">
            <div class="form-brand">
              <img src="/royal-tyres-app-logo.png" alt="Royal Tyres" />
              <span>Staff registration</span>
            </div>
            <p class="eyebrow">Staff registration</p>
            <h2>Create your staff account</h2>
            <p class="subtext">Use Microsoft Outlook or register with your company email.</p>

            <a class="button microsoft" [href]="auth.microsoftLoginUrl()">
              <span class="microsoft-mark">M</span>
              Continue with Microsoft / Outlook
            </a>

            <div class="divider"><span>or create an account</span></div>

            <form [formGroup]="form" (ngSubmit)="submit()">
              <div class="field">
                <label>Full name</label>
                <input formControlName="fullName" autocomplete="name" placeholder="Your full name" />
              </div>
              <div class="field">
                <label>Email</label>
                <input type="email" formControlName="email" autocomplete="email" placeholder="name@royaltyres.co.za" />
              </div>
              <div class="field">
                <label>Password</label>
                <input type="password" formControlName="password" autocomplete="new-password" placeholder="Create a secure password" />
                <small>Use at least 12 characters.</small>
              </div>

              @if (error()) {
                <div class="login-error">{{ error() }}</div>
              }

              <button class="button primary" type="submit" [disabled]="form.invalid || loading()">
                {{ loading() ? 'Creating…' : 'Create account' }}
              </button>
            </form>

            <p class="support">Already registered? <a routerLink="/login">Sign in</a></p>
          </div>
        </section>
      </section>
    </main>
  `,
  styleUrl: './login.component.scss',
})
export class RegisterComponent {
  private readonly fb = inject(FormBuilder);
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly form = this.fb.nonNullable.group({
    fullName: ['', [Validators.required, Validators.minLength(2)]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(12)]],
  });

  submit(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    const value = this.form.getRawValue();
    this.auth.register(value.fullName, value.email, value.password).subscribe({
      next: () => void this.router.navigate(['/dashboard']),
      error: (response) => {
        this.loading.set(false);
        this.error.set(response.error?.detail ?? 'Account could not be created.');
      },
    });
  }
}
