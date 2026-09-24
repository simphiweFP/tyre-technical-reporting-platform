import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Branch, UserAdminService } from '../../core/admin/user-admin.service';
import { ReportDeliveryService } from '../../core/delivery/report-delivery.service';
import { REPORT_CATEGORIES, ReportRecipient } from '../../shared/models/report.models';

interface RecipientFormState {
  company: string;
  contact: string;
  email: string;
  cc: string[];
  branch_code: string;
  category: string;
  escalation_enabled: boolean;
}

@Component({
  selector: 'app-recipients',
  imports: [FormsModule],
  templateUrl: './recipients.component.html',
  styleUrl: './admin.component.scss',
})
export class RecipientsComponent {
  private readonly delivery = inject(ReportDeliveryService);
  private readonly admin = inject(UserAdminService);
  readonly showForm = signal(false);
  readonly query = signal('');
  readonly recipients = signal<ReportRecipient[]>([]);
  readonly branches = signal<Branch[]>([]);
  readonly editing = signal<ReportRecipient | null>(null);
  readonly notice = signal('');
  readonly dialogError = signal('');
  readonly ccDraft = signal('');
  readonly ccError = signal('');
  readonly saving = signal(false);
  readonly categories = REPORT_CATEGORIES;
  newRecipient: RecipientFormState = {
    company: '',
    contact: '',
    email: '',
    cc: [],
    branch_code: 'All Branches',
    category: 'All Categories',
    escalation_enabled: true,
  };
  constructor() {
    void this.load();
  }
  filtered() {
    const q = this.query().toLowerCase();
    return this.recipients().filter(
      (r) =>
        !q || `${r.company} ${r.email} ${r.branch_code} ${r.category}`.toLowerCase().includes(q),
    );
  }
  open(item?: ReportRecipient) {
    this.notice.set('');
    this.dialogError.set('');
    this.ccDraft.set('');
    this.ccError.set('');
    this.editing.set(item ?? null);
    this.newRecipient = item
      ? {
          company: item.company,
          contact: item.contact_name,
          email: item.email,
          cc: item.default_cc,
          branch_code: item.branch_code,
          category: item.category,
          escalation_enabled: item.escalation_enabled,
        }
      : {
          company: '',
          contact: '',
          email: '',
          cc: [],
          branch_code: 'All Branches',
          category: 'All Categories',
          escalation_enabled: true,
        };
    this.showForm.set(true);
  }
  async save() {
    if (this.ccDraft().trim() && !this.addCc()) return;
    const x = this.newRecipient;
    const input = {
      company: x.company,
      contact_name: x.contact,
      email: x.email,
      default_cc: x.cc,
      branch_code: x.branch_code,
      category: x.category,
      escalation_enabled: x.escalation_enabled,
    };
    this.saving.set(true);
    this.dialogError.set('');
    try {
      const current = this.editing();
      const saved = current
        ? await this.delivery.updateRecipient(current.id, {
            ...input,
            is_active: current.is_active,
          })
        : await this.delivery.createRecipient(input);
      this.recipients.update((items) =>
        current ? items.map((i) => (i.id === saved.id ? saved : i)) : [...items, saved],
      );
      this.showForm.set(false);
      this.notice.set(`Recipient rule for ${saved.email} saved successfully.`);
    } catch (error) {
      this.dialogError.set(this.errorMessage(error, 'The recipient rule could not be saved.'));
    } finally {
      this.saving.set(false);
    }
  }
  async toggle(item: ReportRecipient) {
    const r = await this.delivery.setRecipientStatus(item.id, !item.is_active);
    this.recipients.update((x) => x.map((i) => (i.id === r.id ? r : i)));
  }
  async test(item: ReportRecipient) {
    this.notice.set((await this.delivery.testRecipient(item.id)).message);
  }
  addCc(): boolean {
    const addresses = this.ccDraft()
      .split(/[;,]/)
      .map((address) => address.trim().toLowerCase())
      .filter(Boolean);
    if (!addresses.length) return true;
    const invalid = addresses.find((address) => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(address));
    if (invalid) {
      this.ccError.set(`Enter a valid email address: ${invalid}`);
      return false;
    }
    const combined = [...new Set([...this.newRecipient.cc, ...addresses])];
    if (combined.length > 10) {
      this.ccError.set('You can add up to 10 default CC addresses.');
      return false;
    }
    this.newRecipient.cc = combined;
    this.ccDraft.set('');
    this.ccError.set('');
    return true;
  }
  removeCc(address: string): void {
    this.newRecipient.cc = this.newRecipient.cc.filter((item) => item !== address);
    this.ccError.set('');
  }
  private async load() {
    try {
      const [recipients, branches] = await Promise.all([
        this.delivery.recipients(false),
        this.admin.branches(),
      ]);
      this.recipients.set(recipients);
      this.branches.set(branches.filter((branch) => branch.is_active));
    } catch (error) {
      this.notice.set(this.errorMessage(error, 'Recipient data could not be loaded.'));
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
