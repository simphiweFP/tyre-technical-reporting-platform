import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { environment } from '../../../environments/environment';
import { TokenResponse } from '../../shared/models/auth.models';
import { authInterceptor } from './auth.interceptor';
import { AuthService } from './auth.service';

const tokens = (access: string, refresh: string): TokenResponse => ({
  access_token: access,
  refresh_token: refresh,
  token_type: 'bearer',
  user: {
    id: 'user-1',
    email: 'admin@royaltyres.co.za',
    full_name: 'System Administrator',
    job_title: 'Administrator',
    role: 'administrator',
    branch_id: null,
  },
});

describe('authInterceptor', () => {
  let http: HttpClient;
  let controller: HttpTestingController;
  let auth: AuthService;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    controller = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
  });

  afterEach(() => controller.verify());

  it('refreshes an expired access token and retries the API request', () => {
    auth.login('admin@royaltyres.co.za', 'Password123!').subscribe();
    controller.expectOne(`${environment.apiUrl}/auth/login`).flush(tokens('expired', 'refresh-1'));

    http
      .get(`${environment.apiUrl}/reports/records`)
      .subscribe((result) => expect(result).toEqual({ items: [], total: 0 }));

    const failed = controller.expectOne(`${environment.apiUrl}/reports/records`);
    expect(failed.request.headers.get('Authorization')).toBe('Bearer expired');
    failed.flush({ detail: 'Expired token' }, { status: 401, statusText: 'Unauthorized' });

    const refresh = controller.expectOne(`${environment.apiUrl}/auth/refresh`);
    expect(refresh.request.body).toEqual({ refresh_token: 'refresh-1' });
    refresh.flush(tokens('renewed', 'refresh-2'));

    const retried = controller.expectOne(`${environment.apiUrl}/reports/records`);
    expect(retried.request.headers.get('Authorization')).toBe('Bearer renewed');
    retried.flush({ items: [], total: 0 });
  });

  it('uses company session cookies without attaching legacy bearer tokens', () => {
    auth.companyAuth.set(true);
    http.get(`${environment.apiUrl}/reports/records`).subscribe();
    const request = controller.expectOne(`${environment.apiUrl}/reports/records`);
    expect(request.request.withCredentials).toBe(true);
    expect(request.request.headers.has('Authorization')).toBe(false);
    request.flush({ items: [] });
  });

  it('does not send app credentials to another host', () => {
    auth.login('admin@royaltyres.co.za', 'Password123!').subscribe();
    controller.expectOne(`${environment.apiUrl}/auth/login`).flush(tokens('private', 'refresh'));
    http.get('https://unrelated.example/data').subscribe();
    const request = controller.expectOne('https://unrelated.example/data');
    expect(request.request.headers.has('Authorization')).toBe(false);
    expect(request.request.withCredentials).toBe(false);
    request.flush({});
  });

  it('reloads company identity without keeping provider tokens in localStorage', async () => {
    const initialized = auth.ensureInitialized();
    controller.expectOne(`${environment.apiUrl}/auth/config`).flush({ provider: 'rt-auth' });
    await Promise.resolve();
    controller.expectOne(`${environment.apiUrl}/auth/me`).flush(tokens('', '').user);
    await initialized;
    expect(auth.isAuthenticated()).toBe(true);
    expect(auth.companyAuth()).toBe(true);
    expect(auth.accessToken()).toBe('');
    expect(localStorage.getItem('royal-tyres.session')).toBe(null);
  });
});
