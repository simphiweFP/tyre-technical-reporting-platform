import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
interface ManagedUser {
  name: string;
  email: string;
  title: string;
  role: string;
  branch: string;
  active: boolean;
}
@Component({
  selector: 'app-users',
  imports: [FormsModule],
  template: `
    <section class="page">
      <header class="page-header">
        <div>
          <p class="eyebrow">Administration</p>
          <h1>User access</h1>
          <p>Manage who can capture, view and administer technical reports.</p>
        </div>
        <button class="button primary" (click)="showForm.set(true)">＋ Add user</button>
      </header>
      <div class="admin-grid">
        <section class="card list">
          <div class="list-head">
            <strong>{{ users().length }} users</strong
            ><label><span>⌕</span><input [(ngModel)]="query" placeholder="Search users" /></label>
          </div>
          @for (user of filtered(); track user.email) {
            <article>
              <div class="avatar">{{ initials(user.name) }}</div>
              <div class="person">
                <strong>{{ user.name }}</strong
                ><span>{{ user.email }} · {{ user.title }}</span>
              </div>
              <div>
                <strong>{{ roleLabel(user.role) }}</strong
                ><span>{{ user.branch }}</span>
              </div>
              <span class="active" [class.off]="!user.active">{{
                user.active ? 'Active' : 'Inactive'
              }}</span
              ><button class="more" aria-label="User options">•••</button>
            </article>
          }
        </section>
        <aside class="card role-guide">
          <h2>Access model</h2>
          <p>Job titles stay separate from system permissions.</p>
          <dl>
            <div>
              <dt>Administrator</dt>
              <dd>Users, branches, recipients and all reports</dd>
            </div>
            <div>
              <dt>Report Capturer</dt>
              <dd>Technicians and salespeople complete the same workflow</dd>
            </div>
            <div>
              <dt>Viewer</dt>
              <dd>Read-only report history and downloads</dd>
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
              <label>Full name</label><input name="name" [(ngModel)]="newUser.name" required />
            </div>
            <div class="field">
              <label>Email</label
              ><input name="email" [(ngModel)]="newUser.email" type="email" required />
            </div>
            <div class="field">
              <label>Job title</label
              ><input
                name="title"
                [(ngModel)]="newUser.title"
                placeholder="Technician or Salesperson"
              />
            </div>
            <div class="field">
              <label>System role</label
              ><select name="role" [(ngModel)]="newUser.role">
                <option value="report_capturer">Report Capturer</option>
                <option value="viewer">Viewer</option>
                <option value="administrator">Administrator</option>
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
  readonly showForm = signal(false);
  readonly query = signal('');
  readonly users = signal<ManagedUser[]>([
    {
      name: 'System Administrator',
      email: 'admin@royaltyres.co.za',
      title: 'Administrator',
      role: 'administrator',
      branch: 'Phoenix',
      active: true,
    },
    {
      name: 'Thabo Mkhize',
      email: 'thabo@royaltyres.co.za',
      title: 'Technician',
      role: 'report_capturer',
      branch: 'Phoenix',
      active: true,
    },
    {
      name: 'Naledi Khumalo',
      email: 'naledi@royaltyres.co.za',
      title: 'Salesperson',
      role: 'report_capturer',
      branch: 'Durban',
      active: true,
    },
    {
      name: 'Audit User',
      email: 'audit@royaltyres.co.za',
      title: 'Auditor',
      role: 'viewer',
      branch: 'All branches',
      active: false,
    },
  ]);
  newUser = { name: '', email: '', title: '', role: 'report_capturer' };
  filtered(): ManagedUser[] {
    const q = this.query().toLowerCase();
    return this.users().filter(
      (u) => !q || `${u.name} ${u.email} ${u.title}`.toLowerCase().includes(q),
    );
  }
  initials(name: string): string {
    return name
      .split(' ')
      .map((p) => p[0])
      .slice(0, 2)
      .join('');
  }
  roleLabel(role: string): string {
    return role.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }
  addUser(): void {
    if (!this.newUser.name || !this.newUser.email) return;
    this.users.update((v) => [...v, { ...this.newUser, branch: 'Phoenix', active: true }]);
    this.newUser = { name: '', email: '', title: '', role: 'report_capturer' };
    this.showForm.set(false);
  }
}
