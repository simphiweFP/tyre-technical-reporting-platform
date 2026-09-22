import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Branch, ManagedUser, UserAdminService } from '../../core/admin/user-admin.service';
import { UserRole } from '../../shared/models/auth.models';

@Component({
  selector: 'app-users',
  imports: [FormsModule],
  template: `
    <section class="page">
      <header class="page-header">
        <div>
          <p class="eyebrow">Administration</p>
          <h1>User access</h1>
          <p>Create accounts, assign branches and control reporting permissions.</p>
        </div>
        <button class="button primary" (click)="showForm.set(true)">＋ Add user</button>
      </header>
      @if (notice()) {
        <div class="card notice">{{ notice() }}</div>
      }
      <div class="admin-grid">
        <section class="card list">
          <div class="list-head">
            <strong>{{ users().length }} users</strong
            ><label><span>⌕</span><input [(ngModel)]="query" placeholder="Search users" /></label>
          </div>
          @for (user of filtered(); track user.id) {
            <article>
              <div class="avatar">{{ initials(user.full_name) }}</div>
              <div class="person">
                <strong>{{ user.full_name }}</strong
                ><span>{{ user.email }} · {{ user.job_title || 'No job title' }}</span>
              </div>
              <div class="access-fields">
                <select [ngModel]="user.role" (ngModelChange)="changeRole(user, $event)">
                  <option value="pending">Pending</option>
                  <option value="report_capturer">Report Capturer</option>
                  <option value="viewer">Viewer</option>
                  <option value="administrator">Administrator</option></select
                ><select [ngModel]="user.branch_id" (ngModelChange)="changeBranch(user, $event)">
                  <option [ngValue]="null">No branch</option>
                  @for (branch of branches(); track branch.id) {
                    <option [value]="branch.id">{{ branch.name }}</option>
                  }
                </select>
              </div>
              <span class="active" [class.off]="!user.is_active">{{
                user.is_active ? 'Active' : 'Inactive'
              }}</span>
              <div class="actions">
                <button type="button" (click)="toggle(user)">
                  {{ user.is_active ? 'Disable' : 'Enable' }}</button
                ><button type="button" (click)="reset(user)">Reset password</button>
              </div>
            </article>
          }
        </section>
        <aside class="card role-guide">
          <h2>Access model</h2>
          <p>Public registrations begin as Viewer accounts.</p>
          <dl>
            <div>
              <dt>Administrator</dt>
              <dd>Users, recipients and all reports</dd>
            </div>
            <div>
              <dt>Report Capturer</dt>
              <dd>Technicians and salespeople use the same workflow</dd>
            </div>
            <div>
              <dt>Viewer</dt>
              <dd>Read-only history and downloads</dd>
            </div>
          </dl>
        </aside>
      </div>
      @if (showForm()) {
        <div class="modal-backdrop" (click)="showForm.set(false)">
          <form class="modal card" (click)="$event.stopPropagation()" (ngSubmit)="addUser()">
            <div class="modal-head">
              <div>
                <p class="eyebrow">New account</p>
                <h2>Add user</h2>
              </div>
              <button type="button" (click)="showForm.set(false)">×</button>
            </div>
            <div class="field">
              <label>Full name</label><input name="name" [(ngModel)]="newUser.full_name" required />
            </div>
            <div class="field">
              <label>Email</label
              ><input name="email" [(ngModel)]="newUser.email" type="email" required />
            </div>
            <div class="field">
              <label>Job title</label><input name="title" [(ngModel)]="newUser.job_title" />
            </div>
            <div class="field">
              <label>System role</label
              ><select name="role" [(ngModel)]="newUser.role">
                <option value="report_capturer">Report Capturer</option>
                <option value="viewer">Viewer</option>
                <option value="administrator">Administrator</option>
              </select>
            </div>
            <div class="field">
              <label>Branch</label
              ><select name="branch" [(ngModel)]="newUser.branch_id">
                <option [ngValue]="null">No branch</option>
                @for (branch of branches(); track branch.id) {
                  <option [value]="branch.id">{{ branch.name }}</option>
                }
              </select>
            </div>
            <button class="button primary" type="submit">Create user</button>
          </form>
        </div>
      }
    </section>
  `,
  styleUrl: './admin.component.scss',
})
export class UsersComponent {
  private readonly admin = inject(UserAdminService);
  readonly showForm = signal(false);
  readonly query = signal('');
  readonly users = signal<ManagedUser[]>([]);
  readonly branches = signal<Branch[]>([]);
  readonly notice = signal('');
  newUser: {
    email: string;
    full_name: string;
    job_title: string;
    role: UserRole;
    branch_id: string | null;
  } = { email: '', full_name: '', job_title: '', role: 'report_capturer', branch_id: null };
  constructor() {
    void this.load();
  }
  filtered(): ManagedUser[] {
    const q = this.query().toLowerCase();
    return this.users().filter(
      (u) => !q || `${u.full_name} ${u.email} ${u.job_title}`.toLowerCase().includes(q),
    );
  }
  initials(name: string): string {
    return name
      .split(' ')
      .map((part) => part[0])
      .slice(0, 2)
      .join('');
  }
  roleLabel(role: string): string {
    return role.replace('_', ' ').replace(/\b\w/g, (value) => value.toUpperCase());
  }
  branchName(id: string | null): string {
    return this.branches().find((item) => item.id === id)?.name ?? 'No branch';
  }
  async addUser(): Promise<void> {
    if (!this.newUser.full_name || !this.newUser.email) return;
    const created = await this.admin.create({
      ...this.newUser,
      job_title: this.newUser.job_title || null,
    });
    this.users.update((items) => [...items, created]);
    this.notice.set(`User created. Temporary password: ${created.temporary_password}`);
    this.newUser = {
      email: '',
      full_name: '',
      job_title: '',
      role: 'report_capturer',
      branch_id: null,
    };
    this.showForm.set(false);
  }
  async toggle(user: ManagedUser): Promise<void> {
    const updated = await this.admin.update(user.id, { is_active: !user.is_active });
    this.users.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
  }
  async changeRole(user: ManagedUser, role: UserRole): Promise<void> {
    const updated = await this.admin.update(user.id, { role });
    this.replace(updated);
  }
  async changeBranch(user: ManagedUser, branchId: string | null): Promise<void> {
    const updated = await this.admin.update(user.id, { branch_id: branchId });
    this.replace(updated);
  }
  async reset(user: ManagedUser): Promise<void> {
    const result = await this.admin.resetPassword(user.id);
    this.notice.set(`Temporary password for ${user.full_name}: ${result.temporary_password}`);
  }
  private async load(): Promise<void> {
    const [users, branches] = await Promise.all([this.admin.users(), this.admin.branches()]);
    this.users.set(users);
    this.branches.set(branches);
  }
  private replace(updated: ManagedUser): void {
    this.users.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
  }
}
