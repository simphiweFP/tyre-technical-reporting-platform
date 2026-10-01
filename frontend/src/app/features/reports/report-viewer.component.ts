import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuditEvent, SystemAdminService } from '../../core/admin/system-admin.service';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-report-viewer',
  imports: [FormsModule, DatePipe],
  templateUrl: './report-viewer.component.html',
  styleUrl: './report-viewer.component.scss',
})
export class ReportViewerComponent {
  private readonly admin = inject(SystemAdminService);
  readonly auth = inject(AuthService);
  readonly items = signal<AuditEvent[]>([]);
  readonly total = signal(0);
  readonly query = signal('');
  readonly days = signal(7);
  readonly actor = signal('');
  readonly action = signal('');
  readonly message = signal('');
  readonly actors = computed(() =>
    [...new Set(this.items().map((item) => item.actor).filter(Boolean))].sort(),
  );
  readonly actions = computed(() =>
    [...new Set(this.items().map((item) => item.action).filter(Boolean))].sort(),
  );
  readonly todayCount = computed(() => {
    const today = new Date();
    return this.items().filter((item) => {
      const value = new Date(item.occurred_at);
      return (
        value.getFullYear() === today.getFullYear() &&
        value.getMonth() === today.getMonth() &&
        value.getDate() === today.getDate()
      );
    }).length;
  });
  readonly emailCount = computed(() =>
    this.items().filter((item) => item.action.includes('email')).length,
  );
  readonly archiveCount = computed(() =>
    this.items().filter((item) => item.action.includes('archive')).length,
  );
  readonly isCapturer = computed(() => this.auth.hasRole('report_capturer'));

  constructor() {
    void this.load();
  }

  async load(): Promise<void> {
    this.message.set('');
    try {
      const result = await this.admin.auditEvents(
        this.query(),
        this.days(),
        this.actor(),
        this.action(),
      );
      this.items.set(result.items);
      this.total.set(result.total);
    } catch {
      this.message.set('Audit activity could not be loaded.');
    }
  }

  clearFilters(): void {
    this.query.set('');
    this.days.set(7);
    this.actor.set('');
    this.action.set('');
    void this.load();
  }

  summary(item: AuditEvent): string {
    const details = item.details ?? {};
    const recipient = String(details['recipient'] ?? '');
    const status = String(details['status'] ?? '');
    const claim = String(details['claim_reference'] ?? item.entity_id ?? '');

    if (item.action.includes('email_follow_up_sent')) {
      return recipient ? `Follow-up email sent to ${recipient}` : 'Follow-up email sent';
    }
    if (item.action.includes('email_sent')) {
      return recipient ? `Report email accepted for ${recipient}` : 'Report email accepted';
    }
    if (item.action.includes('email_failed')) {
      return recipient ? `Email delivery failed for ${recipient}` : 'Email delivery failed';
    }
    if (item.action.includes('archived')) {
      return claim ? `Technical claim ${claim} archived` : 'Technical claim archived';
    }
    if (item.action.includes('created')) {
      return claim ? `Created ${claim}` : 'Record created';
    }
    if (item.action.includes('updated')) {
      return status ? `Updated status to ${status}` : 'Record updated';
    }
    return this.actionLabel(item.action);
  }

  actionClass(action: string): string {
    if (action.includes('failed') || action.includes('deleted')) return 'danger';
    if (action.includes('email')) return 'email';
    if (action.includes('archive')) return 'archive';
    if (action.includes('created')) return 'created';
    if (action.includes('updated')) return 'updated';
    return 'neutral';
  }

  actionLabel(action: string): string {
    return action
      .replace('report.', '')
      .replaceAll('_', ' ')
      .replace(/\b\w/g, (value) => value.toUpperCase());
  }
}
