import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-register',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './register.component.html',
  styleUrl: './register.component.scss',
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
