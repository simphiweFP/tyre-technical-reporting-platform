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
});
