import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { UserRole } from '../../shared/models/auth.models';
import { AuthService } from './auth.service';
export const authGuard: CanActivateFn = async () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  await auth.ensureInitialized();
  return auth.isAuthenticated() ? true : router.createUrlTree(['/login']);
};
export const roleGuard =
  (...roles: UserRole[]): CanActivateFn =>
  () => {
    const auth = inject(AuthService);
    return auth.hasRole(...roles) ? true : inject(Router).createUrlTree(['/dashboard']);
  };
