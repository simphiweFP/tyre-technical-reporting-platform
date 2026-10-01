import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { UserRole } from '../../shared/models/auth.models';
import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = async () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return (await auth.ensureSession()) ? true : router.createUrlTree(['/login']);
};

export const roleGuard =
  (...roles: UserRole[]): CanActivateFn =>
  async () => {
    const auth = inject(AuthService);
    const router = inject(Router);
    if (!(await auth.ensureSession())) return router.createUrlTree(['/login']);
    return auth.hasRole(...roles) ? true : router.createUrlTree(['/dashboard']);
  };
