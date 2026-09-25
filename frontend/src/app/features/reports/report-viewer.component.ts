import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuditEvent, SystemAdminService } from '../../core/admin/system-admin.service';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-report-viewer',
  imports: [FormsModule],
  templateUrl: './report-viewer.component.html',
  styleUrl: './operations.component.scss',
})
export class ReportViewerComponent {
  private readonly admin = inject(SystemAdminService);
  readonly auth = inject(AuthService);
  readonly items = signal<AuditEvent[]>([]);
  readonly total = signal(0);
  readonly query = signal('');
  readonly days = signal(7);
  readonly message = signal('');
  readonly isCapturer = computed(() => this.auth.hasRole('report_capturer'));

  constructor() {
    void this.load();
  }

  async load(): Promise<void> {
    this.message.set('');
    try {
      const result = await this.admin.auditEvents(this.query(), this.days());
      this.items.set(result.items);
      this.total.set(result.total);
    } catch {
      this.message.set('Audit activity could not be loaded.');
    }
  }

  details(item: AuditEvent): string {
    return (
      Object.entries(item.details)
        .map(([key, value]) => `${key.replaceAll('_', ' ')}: ${value}`)
        .join(', ') || item.entity_type
    );
  }

  actionLabel(action: string): string {
    return action
      .replace('report.', '')
      .replaceAll('_', ' ')
      .replace(/\b\w/g, (value) => value.toUpperCase());
  }
}
