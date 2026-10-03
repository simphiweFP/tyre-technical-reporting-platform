import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { SweetAlertService } from '../../core/ui/sweet-alert.service';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
})
export class LoginComponent {
  private readonly fb = inject(FormBuilder);
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly alerts = inject(SweetAlertService);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]],
  });
  constructor() {
    void this.auth.ensureInitialized();
  }

  submit(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set('');
    this.auth.login(this.form.controls.email.value, this.form.controls.password.value).subscribe({
      next: async () => {
        this.loading.set(false);
        await this.alerts.success('Welcome back', 'Sign-in was successful.');
        void this.router.navigate(['/dashboard']);
      },
      error: (response) => {
        this.loading.set(false);
        const message =
          response.status === 0
            ? 'Cannot reach the API. Check that the backend is running.'
            : response.status === 403
              ? 'Company sign-in is required. Loading RT-Auth sign-in…'
              : 'Email or password is incorrect.';
        if (response.status === 403) void this.auth.retryInitialization();
        this.error.set(message);
        void this.alerts.error('Sign-in failed', message);
      },
    });
  }
}
