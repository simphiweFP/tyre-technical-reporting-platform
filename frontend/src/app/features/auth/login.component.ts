import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <main class="login-page">
      <section class="story-panel">
        <div class="story-content">
          <div class="brand-lockup"><span>RT</span><strong>Royal Tyres</strong></div>
          <p class="kicker">Technical reporting, rebuilt.</p>
          <h1>From inspection to a complete report—without the paperwork.</h1>
          <p>
            Capture every required tyre image, keep technical information together and prepare a
            professional report from any device.
          </p>
          <div class="trust-row">
            <span>✓ Guided capture</span><span>✓ Secure access</span><span>✓ Automatic drafts</span>
          </div>
        </div>
      </section>
      <section class="form-panel">
        <div class="login-card">
          <div class="mobile-logo"><span>RT</span><strong>Royal Tyres</strong></div>
          <p class="eyebrow">Staff portal</p>
          <h2>Welcome back</h2>
          <p class="subtext">Sign in with your Royal Tyres account.</p>
          <a class="button microsoft" [href]="auth.microsoftLoginUrl()"
            >Continue with Microsoft / Outlook</a
          >
          <div class="divider"><span>or use your account</span></div>
          <form [formGroup]="form" (ngSubmit)="submit()">
            <div class="field">
              <label for="email">Email address</label
              ><input
                id="email"
                type="email"
                formControlName="email"
                autocomplete="username"
                placeholder="name@royaltyres.co.za"
              />
            </div>
            <div class="field">
              <label for="password"
                >Password <a routerLink="/forgot-password">Forgot password?</a></label
              ><input
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
