import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { SweetAlertService } from '../../core/ui/sweet-alert.service';

@Component({
  selector: 'app-forgot-password',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './forgot-password.component.html',
  styleUrl: './forgot-password.component.scss',
})
export class ForgotPasswordComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly alerts = inject(SweetAlertService);
  readonly message = signal('');
  readonly form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
  });

  submit(): void {
    this.auth.forgotPassword(this.form.controls.email.value).subscribe({
      next: async () => {
        const message = 'If the account exists, reset instructions have been sent.';
        this.message.set(message);
        await this.alerts.success('Check your email', message);
      },
      error: async () => {
        const message = 'The request could not be completed. Try again.';
        this.message.set(message);
        await this.alerts.error('Request failed', message);
      },
    });
  }
}
