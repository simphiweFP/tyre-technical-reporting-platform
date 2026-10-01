import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { AuthService } from './auth.service';

function cookie(name: string): string {
  const prefix = `${encodeURIComponent(name)}=`;
  const match = document.cookie
    .split(';')
    .map((value) => value.trim())
    .find((value) => value.startsWith(prefix));
  return match ? decodeURIComponent(match.slice(prefix.length)) : '';
}

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  const unsafe = !['GET', 'HEAD', 'OPTIONS'].includes(request.method.toUpperCase());
  const csrf = cookie('rt_tyres_csrf');

  const secured = request.clone({
    withCredentials: true,
    setHeaders: unsafe && csrf ? { 'X-CSRF-Token': csrf } : {},
  });

  return next(secured).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401 && !/\/auth\/(me|company-login)/.test(request.url)) {
        auth.expireSession();
      }
      return throwError(() => error);
    }),
  );
};
