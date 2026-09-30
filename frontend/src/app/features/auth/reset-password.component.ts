import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { SweetAlertService } from '../../core/ui/sweet-alert.service';

@Component({
  selector: 'app-reset-password',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './reset-password.component.html',
  styleUrl: './reset-password.component.scss',
})
export class ResetPasswordComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly alerts = inject(SweetAlertService);
  readonly message = signal('');
  readonly form = this.fb.nonNullable.group({
    password: ['', [Validators.required, Validators.minLength(12)]],
  });

  submit(): void {
    const token = this.route.snapshot.queryParamMap.get('token') ?? '';
    this.auth.resetPassword(token, this.form.controls.password.value).subscribe({
      next: async () => {
        await this.alerts.success('Password updated', 'You can now sign in with your new password.');
        void this.router.navigate(['/login']);
      },
      error: async (response) => {
        const message = response.error?.detail ?? 'Reset link is invalid.';
        this.message.set(message);
        await this.alerts.error('Password not updated', message);
      },
    });
  }
}
