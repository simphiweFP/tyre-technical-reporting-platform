import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-microsoft-callback',
  template: `<main class="callback">
    <h1>Signing you in…</h1>
    <p>{{ message() }}</p>
  </main>`,
  styles: [
    `
      .callback {
        min-height: 100vh;
        display: grid;
        place-content: center;
        text-align: center;
        background: #f4f5f6;
      }
      .callback h1 {
        font-size: 1.5rem;
      }
      .callback p {
        color: #727a80;
      }
    `,
  ],
})
export class MicrosoftCallbackComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  readonly message = signal('Confirming your Microsoft account.');
  constructor() {
    void this.complete();
  }
  private async complete(): Promise<void> {
    const params = new URLSearchParams(location.hash.slice(1));
    history.replaceState(null, '', location.pathname);
    try {
      await this.auth.completeMicrosoft(
        params.get('access_token') ?? '',
        params.get('refresh_token') ?? '',
      );
      await this.router.navigate(['/dashboard']);
    } catch {
      this.message.set('Microsoft sign-in could not be completed. Return to sign in.');
    }
  }
}
