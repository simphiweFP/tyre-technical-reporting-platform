import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-register',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <main class="login-page">
      <section class="story-panel">
        <div class="story-content">
          <div class="brand-lockup"><span>RT</span><strong>Royal Tyres</strong></div>
          <p class="kicker">Technical reporting, rebuilt.</p>
          <h1>Create your secure reporting account.</h1>
          <p>
            New accounts remain pending until an administrator assigns the correct reporting
            permission.
          </p>
        </div>
      </section>
      <section class="form-panel">
        <div class="login-card">
          <p class="eyebrow">Public registration</p>
          <h2>Create account</h2>
          <p class="subtext">Use Microsoft Outlook or register with your email.</p>
          <a class="button microsoft" [href]="auth.microsoftLoginUrl()"
            >Continue with Microsoft / Outlook</a
          >
          <div class="divider"><span>or create a new account</span></div>
          <form [formGroup]="form" (ngSubmit)="submit()">
            <div class="field">
              <label>Full name</label><input formControlName="fullName" autocomplete="name" />
            </div>
            <div class="field">
              <label>Email</label
              ><input type="email" formControlName="email" autocomplete="email" />
            </div>
            <div class="field">
              <label>Password</label
              ><input
                type="password"
                formControlName="password"
                autocomplete="new-password"
              /><small>At least 12 characters.</small>
            </div>
            @if (error()) {
              <div class="login-error">{{ error() }}</div>
            }
            <button class="button primary" [disabled]="form.invalid || loading()">
              {{ loading() ? 'Creating…' : 'Create account' }}
            </button>
          </form>
          <p class="support">Already registered? <a routerLink="/login">Sign in</a></p>
        </div>
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
