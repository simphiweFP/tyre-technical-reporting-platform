import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  const withToken = (token: string | null) =>
    token ? request.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : request;
  const sent = withToken(auth.accessToken());
  const isAuthRequest =
    /\/auth\/(login|register|refresh|logout|forgot-password|reset-password)$/.test(request.url);
  return next(sent).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status !== 401 || isAuthRequest || !auth.refreshToken()) {
        return throwError(() => error);
      }
      return auth.refreshSession().pipe(
        switchMap(() => next(withToken(auth.accessToken()))),
        catchError((refreshError) => {
          auth.expireSession();
          return throwError(() => refreshError);
        }),
      );
    }),
  );
};
