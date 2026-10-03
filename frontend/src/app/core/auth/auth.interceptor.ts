import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';
import { environment } from '../../../environments/environment';
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  const api = new URL(environment.apiUrl, location.origin);
  const target = new URL(request.url, location.origin);
  if (target.origin !== api.origin || !target.pathname.startsWith(api.pathname + '/'))
    return next(request);
  const csrf = document.cookie
    .split('; ')
    .find((cookie) => cookie.startsWith('rt_claim_csrf='))
    ?.split('=')[1];
  request = request.clone({
    withCredentials: true,
    ...(csrf ? { setHeaders: { 'X-CSRF-Token': decodeURIComponent(csrf) } } : {}),
  });
  const withToken = (token: string | null) =>
    token && !auth.companyAuth()
      ? request.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
      : request;
  const sent = withToken(auth.accessToken());
  const isAuthRequest =
    /\/auth\/(login|register|refresh|logout|forgot-password|reset-password)$/.test(request.url);
  return next(sent).pipe(
    catchError((error: HttpErrorResponse) => {
      if (auth.companyAuth()) {
        if (error.status === 401 && !request.url.endsWith('/auth/me')) auth.expireSession();
        return throwError(() => error);
      }
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
