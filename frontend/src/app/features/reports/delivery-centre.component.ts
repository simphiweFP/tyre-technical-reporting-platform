import { AuthService } from '../../core/auth/auth.service';
import { CommonModule } from '@angular/common';
import { Component, OnDestroy, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DeliveryDetail, ReportDeliveryService } from '../../core/delivery/report-delivery.service';
import { DeliveryAttempt } from '../../shared/models/report.models';
import { SweetAlertService } from '../../core/ui/sweet-alert.service';
@Component({
  selector: 'app-delivery-centre',
  imports: [CommonModule, FormsModule],
  templateUrl: './delivery-centre.component.html',
  styleUrl: './delivery-centre.component.scss',
})
export class DeliveryCentreComponent implements OnDestroy {
  readonly auth = inject(AuthService);
  private readonly delivery = inject(ReportDeliveryService);
  private readonly alerts = inject(SweetAlertService);
  readonly items = signal<DeliveryAttempt[]>([]);
  readonly total = signal(0);
  readonly query = signal('');
  readonly status = signal('');
  readonly message = signal('');
  readonly selected = signal<DeliveryDetail | null>(null);
  readonly detailsBusy = signal(false);
  readonly followUpMessage = signal('');
  readonly followUpBusy = signal(false);
  private searchTimer?: ReturnType<typeof setTimeout>;
  private readonly refreshTimer = window.setInterval(() => void this.load(), 30_000);

  constructor() {
    void this.load();
  }

  ngOnDestroy(): void {
    window.clearInterval(this.refreshTimer);
    if (this.searchTimer) clearTimeout(this.searchTimer);
  }

  async load() {
    try {
      const r = await this.delivery.deliveries(this.query(), this.status());
      this.items.set(r.items);
      this.total.set(r.total);
    } catch {
      this.message.set('Delivery history could not be loaded.');
    }
  }

  async retry(id: string) {
    if (
      !(await this.alerts.confirm(
        'Retry failed delivery?',
        'The original saved email and PDF snapshot will be sent again.',
        'Retry email',
        'warning',
      ))
    )
      return;
    this.message.set('');
    this.alerts.loading('Retrying email…', 'Using the original delivery snapshot.');
    try {
      const result = await this.delivery.retry(id);
      this.alerts.close();
      const message =
        result.status === 'Sent' ? 'Email sent successfully.' : 'Email retry attempted.';
      this.message.set(message);
      await this.alerts.success('Delivery retry complete', message);
      await this.load();
      if (this.selected()?.id === id) await this.view(id);
    } catch {
      this.alerts.close();
      const message = 'Email could not be retried. Open the delivery to view the latest error.';
      this.message.set(message);
      await this.alerts.error('Retry failed', message);
      await this.load();
    }
  }

  async view(id: string) {
    this.detailsBusy.set(true);
    try {
      this.selected.set(await this.delivery.deliveryDetails(id));
    } catch {
      this.message.set('Delivery details could not be loaded.');
    } finally {
      this.detailsBusy.set(false);
    }
  }

  closeDetails() {
    this.selected.set(null);
    this.followUpMessage.set('');
  }

  async viewPdf(id: string) {
    this.alerts.loading('Loading attachment…', 'Loading the saved report securely.');
    try {
      const detail = this.selected();
      if (
        detail &&
        (detail.attachment_name.endsWith('.csv') ||
          detail.attachment_name.endsWith('.zip') ||
          detail.attachment_name.endsWith('.xlsx'))
      )
        await this.delivery.downloadAttachment(id, detail.attachment_name);
      else await this.delivery.openDeliveryPdf(id);
      this.alerts.close();
    } catch {
      this.alerts.close();
      await this.alerts.error(
        'PDF could not be opened',
        'The saved report could not be loaded. Please try again.',
      );
    }
  }

  async sendFollowUp(id: string) {
    const message = this.followUpMessage().trim();
    if (!message) {
      await this.alerts.warning('Message required', 'Type your follow-up message before sending.');
      return;
    }
    if (
      !(await this.alerts.confirm(
        'Send follow-up?',
        'Your message will be sent as a reply to the original email thread.',
        'Send follow-up',
      ))
    )
      return;
    this.followUpBusy.set(true);
    this.message.set('');
    this.alerts.loading(
      'Sending follow-up…',
      'Keeping the message in the original email conversation.',
    );
    try {
      await this.delivery.followUp(id, message);
      this.alerts.close();
      this.message.set('');
      this.followUpMessage.set('');
      this.selected.set(await this.delivery.deliveryDetails(id));
      await this.alerts.success('Follow-up sent', 'Your message was sent successfully.');
    } catch {
      this.alerts.close();
      this.message.set('Follow-up email could not be sent.');
      await this.alerts.error('Follow-up failed', 'The follow-up email could not be delivered.');
    } finally {
      this.followUpBusy.set(false);
    }
  }

  async remove(id: string) {
    if (
      !(await this.alerts.confirm(
        'Remove delivery record?',
        'This is a soft delete. The record stays in the database for audit history.',
        'Remove record',
        'warning',
        true,
      ))
    )
      return;
    try {
      await this.delivery.softDeleteDelivery(id);
      if (this.selected()?.id === id) this.closeDetails();
      this.message.set('Delivery record removed from the active list.');
      await this.load();
      await this.alerts.success(
        'Delivery removed',
        'The record is hidden from the active Delivery Centre and retained for audit.',
      );
    } catch {
      this.message.set('Delivery record could not be removed.');
      await this.alerts.error('Delete failed', 'The delivery record could not be removed.');
    }
  }

  searchChanged(value: string) {
    this.query.set(value);
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => void this.load(), 300);
  }

  deliveryStatusLabel(status: string): string {
    return status === 'Sent' ? 'Accepted' : status;
  }

  clear() {
    this.query.set('');
    this.status.set('');
    void this.load();
  }
}
