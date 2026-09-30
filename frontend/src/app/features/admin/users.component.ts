import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Branch, ManagedUser, UserAdminService } from '../../core/admin/user-admin.service';
import { UserRole } from '../../shared/models/auth.models';
import { SweetAlertService } from '../../core/ui/sweet-alert.service';

interface UserForm {
  email: string;
  full_name: string;
  job_title: string;
  role: UserRole;
  branch_id: string | null;
}
const emptyUser = (): UserForm => ({
  email: '',
  full_name: '',
  job_title: '',
  role: 'report_capturer',
  branch_id: null,
});

@Component({
  selector: 'app-users',
  imports: [FormsModule],
  templateUrl: './users.component.html',
  styleUrl: './users.component.scss',
})
export class UsersComponent {
  private readonly admin = inject(UserAdminService);
  private readonly alerts = inject(SweetAlertService);
  readonly showForm = signal(false);
  readonly editing = signal<ManagedUser | null>(null);
  readonly query = signal('');
  readonly users = signal<ManagedUser[]>([]);
  readonly branches = signal<Branch[]>([]);
  readonly notice = signal('');
  readonly error = signal('');
  readonly saving = signal(false);
  form = emptyUser();
  constructor() {
    void this.load();
  }
  filtered(): ManagedUser[] {
    const query = this.query().toLowerCase();
    return this.users().filter(
      (user) =>
        !query || `${user.full_name} ${user.email} ${user.role}`.toLowerCase().includes(query),
    );
  }
  username(user: ManagedUser): string {
    return user.email.split('@')[0];
  }
  roleLabel(role: string): string {
    return role.replace('_', ' ').replace(/\b\w/g, (value) => value.toUpperCase());
  }
  branchName(id: string | null): string {
    return this.branches().find((branch) => branch.id === id)?.name ?? 'All Branches';
  }
  open(user?: ManagedUser): void {
    this.error.set('');
    this.editing.set(user ?? null);
    this.form = user
      ? {
          email: user.email,
          full_name: user.full_name,
          job_title: user.job_title ?? '',
          role: user.role,
          branch_id: user.branch_id,
        }
      : emptyUser();
    this.showForm.set(true);
  }
  async save(): Promise<void> {
    const fullName = this.form.full_name.trim();
    const email = this.form.email.trim().toLowerCase();
    const jobTitle = this.form.job_title.trim();
    if (fullName.length < 2 || fullName.length > 150 || (!this.editing() && !email)) return;

    this.error.set('');
    this.saving.set(true);
    try {
      const current = this.editing();
      if (current) {
        const updated = await this.admin.update(current.id, {
          full_name: fullName,
          job_title: jobTitle || null,
          role: this.form.role,
          branch_id: this.form.branch_id,
        });
        this.replace(updated);
        this.notice.set(`${updated.full_name} was updated.`);
        await this.alerts.success('User updated', `${updated.full_name}'s access details were saved.`);
      } else {
        const created = await this.admin.create({
          email,
          full_name: fullName,
          job_title: jobTitle || null,
          role: this.form.role,
          branch_id: this.form.branch_id,
        });
        this.users.update((users) => [...users, created]);
        this.notice.set(`User created. Temporary password: ${created.temporary_password}`);
        await this.alerts.info('User created', `Temporary password for ${created.full_name}: ${created.temporary_password}`);
      }
      this.showForm.set(false);
    } catch (error) {
      const message = this.errorMessage(error, 'The user could not be saved.');
      this.error.set(message);
      await this.alerts.error('User not saved', message);
    } finally {
      this.saving.set(false);
    }
  }
  async toggle(user: ManagedUser): Promise<void> {
    if (!(await this.alerts.confirm(
      user.is_active ? 'Disable user?' : 'Enable user?',
      `${user.full_name} will ${user.is_active ? 'lose' : 'regain'} access to the platform.`,
      user.is_active ? 'Disable user' : 'Enable user',
      'warning',
      user.is_active,
    ))) return;
    try {
      const updated = await this.admin.update(user.id, { is_active: !user.is_active });
      this.replace(updated);
      await this.alerts.success(updated.is_active ? 'User enabled' : 'User disabled', `${updated.full_name}'s access was updated.`);
    } catch {
      await this.alerts.error('User not updated', 'The user status could not be changed.');
    }
  }
  async reset(user: ManagedUser): Promise<void> {
    if (!(await this.alerts.confirm('Reset password?', `Create a new temporary password for ${user.full_name}?`, 'Reset password', 'warning'))) return;
    try {
      const result = await this.admin.resetPassword(user.id);
      this.notice.set(`Temporary password for ${user.full_name}: ${result.temporary_password}`);
      await this.alerts.info('Password reset', `Temporary password for ${user.full_name}: ${result.temporary_password}`);
    } catch {
      await this.alerts.error('Reset failed', 'A temporary password could not be created.');
    }
  }
  private async load(): Promise<void> {
    try {
      const [users, branches] = await Promise.all([this.admin.users(), this.admin.branches()]);
      this.users.set(users);
      this.branches.set(branches);
    } catch {
      this.error.set('Users and branches could not be loaded.');
    }
  }
  private errorMessage(error: unknown, fallback: string): string {
    if (!(error instanceof HttpErrorResponse)) return fallback;
    const detail = error.error?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          const location = Array.isArray(item?.loc) ? item.loc : [];
          const field = String(location.at(-1) ?? '').replace(/_/g, ' ');
          const message = typeof item?.msg === 'string' ? item.msg : 'Invalid value';
          return field ? `${field}: ${message}` : message;
        })
        .filter(Boolean);
      if (messages.length) return messages.join(' ');
    }
    return fallback;
  }

  private replace(user: ManagedUser): void {
    this.users.update((users) => users.map((item) => (item.id === user.id ? user : item)));
  }
}
