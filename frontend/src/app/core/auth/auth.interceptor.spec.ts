import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { environment } from '../../../environments/environment';
import { authInterceptor } from './auth.interceptor';

describe('authInterceptor', () => {
  let http: HttpClient;
  let controller: HttpTestingController;

  beforeEach(() => {
    document.cookie = 'rt_tyres_csrf=test-csrf; path=/';
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    controller = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    document.cookie = 'rt_tyres_csrf=; Max-Age=0; path=/';
    controller.verify();
  });

  it('sends credentials on API requests', () => {
    http.get(`${environment.apiUrl}/reports/records`).subscribe();

    const request = controller.expectOne(`${environment.apiUrl}/reports/records`);
    expect(request.request.withCredentials).toBeTrue();
    expect(request.request.headers.has('Authorization')).toBeFalse();
    request.flush({ items: [], total: 0 });
  });

  it('adds CSRF header to unsafe requests', () => {
    http.post(`${environment.apiUrl}/reports/records`, {}).subscribe();

    const request = controller.expectOne(`${environment.apiUrl}/reports/records`);
    expect(request.request.withCredentials).toBeTrue();
    expect(request.request.headers.get('X-CSRF-Token')).toBe('test-csrf');
    request.flush({});
  });
});
