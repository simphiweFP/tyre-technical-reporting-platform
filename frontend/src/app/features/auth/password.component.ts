import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-forgot-password',
  imports: [ReactiveFormsModule, RouterLink],
  template: `<main class="login-page">
    <section class="form-panel">
      <div class="login-card">
        <p class="eyebrow">Account recovery</p>
        <h2>Reset password</h2>
        <p class="subtext">Enter your account email. We will send a time-limited reset link.</p>
        <form [formGroup]="form" (ngSubmit)="submit()">
          <div class="field">
            <label>Email</label><input type="email" formControlName="email" />
          </div>
          <button class="button primary" [disabled]="form.invalid">Send reset link</button>
        </form>
        @if (message()) {
          <div class="login-error">{{ message() }}</div>
        }
        <p class="support"><a routerLink="/login">Back to sign in</a></p>
      </div>
    </section>
  </main>`,
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
  imports: [ReactiveFormsModule],
  template: `<main class="login-page">
    <section class="form-panel">
      <div class="login-card">
        <p class="eyebrow">Account recovery</p>
        <h2>Choose a new password</h2>
        <form [formGroup]="form" (ngSubmit)="submit()">
          <div class="field">
            <label>New password</label
            ><input type="password" formControlName="password" autocomplete="new-password" />
          </div>
          <button class="button primary" [disabled]="form.invalid">Update password</button>
        </form>
        @if (message()) {
          <div class="login-error">{{ message() }}</div>
        }
      </div>
    </section>
  </main>`,
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
