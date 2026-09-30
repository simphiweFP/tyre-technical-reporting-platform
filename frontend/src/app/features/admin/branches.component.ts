import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Branch, UserAdminService } from '../../core/admin/user-admin.service';
import { SweetAlertService } from '../../core/ui/sweet-alert.service';
@Component({
  selector: 'app-branches',
  imports: [FormsModule],
  templateUrl: './branches.component.html',
  styleUrl: './branches.component.scss',
})
export class BranchesComponent {
  private readonly admin = inject(UserAdminService);
  private readonly alerts = inject(SweetAlertService);
  readonly branches = signal<Branch[]>([]);
  readonly query = signal('');
  readonly showForm = signal(false);
  readonly editing = signal<Branch | null>(null);
  readonly notice = signal('');
  readonly dialogError = signal('');
  readonly saving = signal(false);
  form = { code: '', name: '', routing_email: '' };
  constructor() {
    void this.load();
  }
  filtered() {
    const q = this.query().toLowerCase();
    return this.branches().filter((b) => !q || `${b.name} ${b.code}`.toLowerCase().includes(q));
  }
  open(item?: Branch) {
    this.notice.set('');
    this.dialogError.set('');
    this.editing.set(item ?? null);
    this.form = item
      ? { code: item.code, name: item.name, routing_email: item.routing_email }
      : { code: '', name: '', routing_email: '' };
    this.showForm.set(true);
  }
  async save() {
    this.saving.set(true);
    this.dialogError.set('');
    try {
      const current = this.editing();
      const input = {
        code: this.form.code.trim(),
        name: this.form.name.trim(),
        routing_email: this.form.routing_email.trim() || null,
      };
      const saved = current
        ? await this.admin.updateBranch(current.id, input)
        : await this.admin.createBranch(input);
      this.branches.update((x) =>
        current ? x.map((b) => (b.id === saved.id ? saved : b)) : [...x, saved],
      );
      this.showForm.set(false);
      this.notice.set(`Branch ${saved.code} saved successfully.`);
      await this.alerts.success('Branch saved', `${saved.name} (${saved.code}) is ready to use.`);
    } catch (error) {
      const message = this.errorMessage(error, 'The branch could not be saved.');
      this.dialogError.set(message);
      await this.alerts.error('Branch not saved', message);
    } finally {
      this.saving.set(false);
    }
  }
  async toggle(item: Branch) {
    const action = item.is_active ? 'disable' : 'enable';
    if (!(await this.alerts.confirm(
      `${item.is_active ? 'Disable' : 'Enable'} branch?`,
      `${item.name} will be ${action}d for new report activity.`,
      item.is_active ? 'Disable branch' : 'Enable branch',
      'warning',
      item.is_active,
    ))) return;
    try {
      const updated = await this.admin.updateBranch(item.id, { is_active: !item.is_active });
      this.branches.update((x) => x.map((b) => (b.id === updated.id ? updated : b)));
      await this.alerts.success(
        updated.is_active ? 'Branch enabled' : 'Branch disabled',
        `${updated.name} was updated successfully.`,
      );
    } catch (error) {
      await this.alerts.error('Branch not updated', this.errorMessage(error, 'The branch status could not be changed.'));
    }
  }
  private async load() {
    try {
      this.branches.set(await this.admin.branches());
    } catch (error) {
      this.notice.set(this.errorMessage(error, 'Branches could not be loaded.'));
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
}
