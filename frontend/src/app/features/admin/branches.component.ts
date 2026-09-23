import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Branch, UserAdminService } from '../../core/admin/user-admin.service';
@Component({
  selector: 'app-branches',
  imports: [FormsModule],
  templateUrl: './branches.component.html',
  styleUrl: './admin.component.scss',
})
export class BranchesComponent {
  private readonly admin = inject(UserAdminService);
  readonly branches = signal<Branch[]>([]);
  readonly query = signal('');
  readonly showForm = signal(false);
  readonly editing = signal<Branch | null>(null);
  readonly notice = signal('');
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
    this.editing.set(item ?? null);
    this.form = item
      ? { code: item.code, name: item.name, routing_email: item.routing_email }
      : { code: '', name: '', routing_email: '' };
    this.showForm.set(true);
  }
  async save() {
    this.saving.set(true);
    this.notice.set('');
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
    } catch (error) {
      this.notice.set(this.errorMessage(error, 'The branch could not be saved.'));
    } finally {
      this.saving.set(false);
    }
  }
  async toggle(item: Branch) {
    const updated = await this.admin.updateBranch(item.id, { is_active: !item.is_active });
    this.branches.update((x) => x.map((b) => (b.id === updated.id ? updated : b)));
  }
  private async load() {
    try {
      this.branches.set(await this.admin.branches());
    } catch (error) {
      this.notice.set(this.errorMessage(error, 'Branches could not be loaded.'));
    }
  }
  private errorMessage(error: unknown, fallback: string): string {
    if (error instanceof HttpErrorResponse && typeof error.error?.detail === 'string') {
      return error.error.detail;
    }
    return fallback;
  }
}
