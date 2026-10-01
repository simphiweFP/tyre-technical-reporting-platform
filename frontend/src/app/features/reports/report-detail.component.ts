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
      await this.alerts.warning(
        'Recipient required',
        'Select a recipient before sending this report.',
      );
      return;
    }

    const recipient = this.recipients().find((item) => item.id === recipientId);
    if (
      !(await this.alerts.confirmReportSend(
        recipient?.email ?? 'Selected recipient',
        r.claimReference,
      ))
    ) {
      return;
    }

    this.busy.set('send');
    this.message.set('');
    this.alerts.sending();

    try {
      const result = await this.delivery.deliver(r, recipientId);

      const updated = {
        ...r,
        status:
          result.status === 'Sent'
            ? ('Email Sent' as const)
            : result.status === 'Failed'
              ? ('Email Failed' as const)
              : ('Submitted' as const),
      };
      await this.store.saveNow(updated);
      this.report.set(updated);

      // Always reload delivery history. Failed and retrying attempts are
      // reporting records too and must remain visible in Delivery Centre.
      await this.loadDeliveries(r.claimReference);
      this.alerts.close();

      if (result.status === 'Sent') {
        this.message.set(`Email accepted for ${result.recipient_email}.`);
        await this.alerts.success(
          'Report accepted',
          `${r.claimReference} was accepted by the mail server for ${result.recipient_email}.`,
        );
        return;
      }

      if (result.status === 'Failed') {
        this.message.set(
          'Email delivery failed. The failed attempt was saved in Delivery Centre.',
        );
        await this.alerts.error(
          'Email delivery failed',
          result.error_message ||
            'The recipient could not receive the email. The failed attempt is available in Delivery Centre for reporting and retry.',
        );
        return;
      }

      this.message.set(
        'Email delivery is waiting for retry. Track it in Delivery Centre.',
      );
      await this.alerts.warning(
        'Email not delivered yet',
        result.error_message
          ? `The delivery is scheduled for retry. ${result.error_message}`
          : 'The delivery is scheduled for retry and is visible in Delivery Centre.',
      );
    } catch {
      // A request can fail after the server has already persisted an attempt.
      // Refresh history so any saved failure is still surfaced to the user.
      await this.loadDeliveries(r.claimReference);
      this.alerts.close();

      const latest = this.deliveries()[0];
      if (latest && latest.status === 'Failed') {
        const updated = { ...r, status: 'Email Failed' as const };
        this.report.set(updated);
        this.message.set(
          'Email delivery failed. The failed attempt was saved in Delivery Centre.',
        );
        await this.alerts.error(
          'Email delivery failed',
          latest.error_message ||
            'The failed delivery is available in Delivery Centre for reporting and retry.',
        );
      } else {
        await this.alerts.error(
          'Send failed',
          'The report could not be delivered. Check Delivery Centre for any saved delivery attempt.',
        );
      }
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
