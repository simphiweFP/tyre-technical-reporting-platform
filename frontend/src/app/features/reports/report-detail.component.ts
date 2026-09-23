import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ReportStore } from '../../core/data/report.store';
import { ReportDeliveryService } from '../../core/delivery/report-delivery.service';
import { ReportIntelligenceService } from '../../core/media/report-intelligence.service';
import { AuthService } from '../../core/auth/auth.service';
import {
  DeliveryAttempt,
  ReportRecipient,
  TechnicalReport,
} from '../../shared/models/report.models';

@Component({
  selector: 'app-report-detail',
  templateUrl: './report-detail.component.html',
  styleUrl: './operations.component.scss',
})
export class ReportDetailComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly store = inject(ReportStore);
  private readonly intelligence = inject(ReportIntelligenceService);
  private readonly delivery = inject(ReportDeliveryService);
  readonly auth = inject(AuthService);
  readonly report = signal<TechnicalReport | null>(null);
  readonly deliveries = signal<DeliveryAttempt[]>([]);
  readonly recipients = signal<ReportRecipient[]>([]);
  readonly selectedRecipient = signal('');
  readonly busy = signal('');
  readonly message = signal('');
  constructor() {
    void this.load();
  }
  async load() {
    try {
      const item = await this.store.loadOne(this.route.snapshot.paramMap.get('id')!);
      this.report.set(item);
      await this.loadDeliveries(item.claimReference);
    } catch {
      this.message.set('The report could not be loaded.');
      return;
    }
    if (!this.auth.hasRole('administrator', 'report_capturer')) return;
    try {
      const item = this.report()!;
      const recipients = await this.delivery.recipients(true, item.branch, item.category);
      this.recipients.set(recipients);
      if (recipients.length) this.selectedRecipient.set(recipients[0].id);
    } catch {
      this.recipients.set([]);
    }
  }
  async generatePdf() {
    const r = this.report();
    if (!r) return;
    this.busy.set('pdf');
    try {
      await this.intelligence.downloadPdf(r);
      const updated = { ...r, status: 'Ready to Submit' as const };
      await this.store.saveNow(updated);
      this.report.set(updated);
      this.message.set('PDF generated and report marked ready.');
    } finally {
      this.busy.set('');
    }
  }
  async send() {
    const r = this.report();
    if (!r || !this.selectedRecipient()) return;
    this.busy.set('send');
    try {
      const result = await this.delivery.deliver(r, this.selectedRecipient());
      const updated = { ...r, status: 'Submitted' as const };
      await this.store.saveNow(updated);
      this.report.set(updated);
      this.message.set(`Report queued for delivery to ${result.recipient_email}.`);
      await this.loadDeliveries(r.claimReference);
    } finally {
      this.busy.set('');
    }
  }
  async retry(attempt: DeliveryAttempt) {
    this.busy.set(`retry-${attempt.id}`);
    try {
      await this.delivery.retry(attempt.id);
      await this.loadDeliveries(attempt.claim_reference);
      this.message.set(`Delivery to ${attempt.recipient_email} was queued for retry.`);
    } finally {
      this.busy.set('');
    }
  }
  async archive() {
    const r = this.report();
    if (!r) return;
    this.busy.set('archive');
    try {
      await this.store.archive(r.id);
      await this.router.navigate(['/reports']);
    } finally {
      this.busy.set('');
    }
  }
  photoUrl(category: string) {
    return this.report()?.photos.find((p) => p.category === category)?.previewUrl || '';
  }

  private async loadDeliveries(claimReference: string) {
    try {
      this.deliveries.set(await this.delivery.history(claimReference));
    } catch {
      this.deliveries.set([]);
    }
  }
}
