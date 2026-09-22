import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { UserRole } from '../../shared/models/auth.models';

export interface ManagedUser {
  id: string;
  email: string;
  full_name: string;
  job_title: string | null;
  role: UserRole;
  branch_id: string | null;
  is_active: boolean;
}
export interface Branch {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
}
export interface UserInput {
  email: string;
  full_name: string;
  job_title: string | null;
  role: UserRole;
  branch_id: string | null;
}

@Injectable({ providedIn: 'root' })
export class UserAdminService {
  private readonly http = inject(HttpClient);
  users(): Promise<ManagedUser[]> {
    return firstValueFrom(this.http.get<ManagedUser[]>(`${environment.apiUrl}/auth/users`));
  }
  branches(): Promise<Branch[]> {
    return firstValueFrom(this.http.get<Branch[]>(`${environment.apiUrl}/auth/branches`));
  }
  create(input: UserInput): Promise<ManagedUser & { temporary_password: string }> {
    return firstValueFrom(
      this.http.post<ManagedUser & { temporary_password: string }>(
        `${environment.apiUrl}/auth/users`,
        input,
      ),
    );
  }
  update(id: string, changes: Partial<ManagedUser>): Promise<ManagedUser> {
    return firstValueFrom(
      this.http.patch<ManagedUser>(`${environment.apiUrl}/auth/users/${id}`, changes),
    );
  }
  resetPassword(id: string): Promise<{ temporary_password: string }> {
    return firstValueFrom(
      this.http.post<{ temporary_password: string }>(
        `${environment.apiUrl}/auth/users/${id}/reset-password`,
        null,
      ),
    );
  }
}
