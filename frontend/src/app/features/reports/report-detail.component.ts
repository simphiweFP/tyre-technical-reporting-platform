import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ReportStore } from '../../core/data/report.store';
import { ReportDeliveryService } from '../../core/delivery/report-delivery.service';
import { ReportIntelligenceService } from '../../core/media/report-intelligence.service';
import { AuthService } from '../../core/auth/auth.service';
import { SweetAlertService } from '../../core/ui/sweet-alert.service';
import {
  DeliveryAttempt,
  ReportRecipient,
  TechnicalReport,
} from '../../shared/models/report.models';

@Component({
  selector: 'app-report-detail',
  templateUrl: './report-detail.component.html',
  styleUrl: './report-detail.component.scss',
})
export class ReportDetailComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly store = inject(ReportStore);
  private readonly intelligence = inject(ReportIntelligenceService);
  private readonly delivery = inject(ReportDeliveryService);
  readonly auth = inject(AuthService);
  private readonly alerts = inject(SweetAlertService);
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
    this.message.set('');
    this.alerts.loading('Generating PDF…', 'Building the Royal Tyres technical report.');
    try {
      await this.intelligence.downloadPdf(r);
      const updated = { ...r, status: 'Ready to Submit' as const };
      await this.store.saveNow(updated);
      this.report.set(updated);
      this.alerts.close();
      this.message.set('PDF generated and report marked ready.');
      await this.alerts.success('PDF ready', `${r.claimReference} was generated successfully.`);
    } catch (error) {
      console.error('PDF generation failed', error);
      this.alerts.close();
      this.message.set('PDF generation failed. Please try again.');
      await this.alerts.error('PDF failed', 'The technical report PDF could not be generated.');
    } finally {
      this.busy.set('');
    }
  }
  async send() {
    const r = this.report();
    const recipientId = this.selectedRecipient();
    if (!r || !recipientId) {
      await this.alerts.warning('Recipient required', 'Select a recipient before sending this report.');
      return;
    }
    const recipient = this.recipients().find((item) => item.id === recipientId);
    if (!(await this.alerts.confirmReportSend(recipient?.email ?? 'Selected recipient', r.claimReference))) return;
    this.busy.set('send');
    this.alerts.sending();
    try {
      const result = await this.delivery.deliver(r, recipientId);
      const updated = { ...r, status: 'Submitted' as const };
      await this.store.saveNow(updated);
      this.report.set(updated);
      this.alerts.close();
      this.message.set(`Report sent to ${result.recipient_email}.`);
      await this.loadDeliveries(r.claimReference);
      await this.alerts.success('Report sent', `${r.claimReference} was sent to ${result.recipient_email}.`);
    } catch {
      this.alerts.close();
      await this.alerts.error('Send failed', 'The report could not be delivered.');
    } finally {
      this.busy.set('');
    }
  }
  async retry(attempt: DeliveryAttempt) {
    if (!(await this.alerts.confirm('Retry delivery?', `Retry the original email to ${attempt.recipient_email}?`, 'Retry email', 'warning'))) return;
    this.busy.set(`retry-${attempt.id}`);
    this.alerts.loading('Retrying email…', 'Using the original saved delivery snapshot.');
    try {
      await this.delivery.retry(attempt.id);
      this.alerts.close();
      await this.loadDeliveries(attempt.claim_reference);
      this.message.set(`Delivery to ${attempt.recipient_email} was retried.`);
      await this.alerts.success('Retry complete', `Delivery to ${attempt.recipient_email} was retried.`);
    } catch {
      this.alerts.close();
      await this.alerts.error('Retry failed', 'The email could not be retried.');
    } finally {
      this.busy.set('');
    }
  }
  async archive() {
    const r = this.report();
    if (!r) return;
    if (!(await this.alerts.confirm(
      'Archive technical report?',
      `${r.claimReference} will leave the active list but remain available for audit history.`,
      'Archive report',
      'warning',
      true,
    ))) return;
    this.busy.set('archive');
    try {
      await this.store.archive(r.id);
      await this.alerts.success('Report archived', `${r.claimReference} was archived successfully.`);
      await this.router.navigate(['/reports']);
    } catch {
      await this.alerts.error('Archive failed', 'The report could not be archived.');
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
