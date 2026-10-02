import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { OfflineDataService } from '../offline/offline-data.service';
import { DeliveryAttempt, TechnicalReport } from '../../shared/models/report.models';

export interface DeliveryFollowUp {
  body: string;
  sent_at: string;
  message_id: string;
  in_reply_to: string | null;
  recipient: string;
}

export interface DeliveryDetail {
  id: string;
  claim_reference: string;
  from: string;
  to: string[];
  cc: string[];
  subject: string;
  body: string;
  attachment_name: string;
  document_type: string;
  status: string;
  message_id: string | null;
  error_message: string | null;
  attempt_count: number;
  created_at: string;
  last_attempt_at: string;
  follow_ups: DeliveryFollowUp[];
}

@Injectable({ providedIn: 'root' })
export class ReportDeliveryService {
  private readonly http = inject(HttpClient);
  private readonly offline = inject(OfflineDataService);

  deliveries(query = '', status = ''): Promise<{ items: DeliveryAttempt[]; total: number }> {
    return firstValueFrom(
      this.http.get<{ items: DeliveryAttempt[]; total: number }>(
        `${environment.apiUrl}/deliveries`,
        { params: { query, delivery_status: status } },
      ),
    );
  }

  deliver(
    report: TechnicalReport,
    recipientEmail: string,
    cc: string[] = [],
  ): Promise<DeliveryAttempt> {
    return firstValueFrom(
      this.http.post<DeliveryAttempt>(`${environment.apiUrl}/reports/deliver`, {
        recipient_email: recipientEmail,
        report,
        cc,
      }),
    );
  }

  history(claimReference: string): Promise<DeliveryAttempt[]> {
    return firstValueFrom(
      this.http.get<DeliveryAttempt[]>(
        `${environment.apiUrl}/reports/${encodeURIComponent(claimReference)}/deliveries`,
      ),
    );
  }

  retry(deliveryId: string): Promise<DeliveryAttempt> {
    return firstValueFrom(
      this.http.post<DeliveryAttempt>(
        `${environment.apiUrl}/reports/deliveries/${deliveryId}/retry`,
        null,
      ),
    );
  }

  deliveryDetails(deliveryId: string): Promise<DeliveryDetail> {
    return firstValueFrom(
      this.http.get<DeliveryDetail>(`${environment.apiUrl}/deliveries/${deliveryId}/details`),
    );
  }

  async downloadAttachment(deliveryId: string, filename: string): Promise<void> {
    const blob = await firstValueFrom(
      this.http.get(`${environment.apiUrl}/deliveries/${deliveryId}/pdf`, { responseType: 'blob' }),
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }
  async openDeliveryPdf(deliveryId: string): Promise<void> {
    // Open the tab immediately from the user's click so browsers do not treat
    // the later authenticated HTTP response as a popup. Using "noopener" in
    // window.open can also return null even when a tab opened, which caused a
    // false "PDF could not be opened" alert.
    const preview = window.open('about:blank', '_blank');
    if (!preview) {
      throw new Error('The browser blocked the PDF preview window.');
    }

    preview.opener = null;
    let url = '';

    try {
      const blob = await firstValueFrom(
        this.http.get(`${environment.apiUrl}/deliveries/${deliveryId}/pdf`, {
          responseType: 'blob',
        }),
      );
      url = URL.createObjectURL(blob);
      preview.location.replace(url);
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
      preview.close();
      if (url) URL.revokeObjectURL(url);
      throw error;
    }
  }

  followUp(
    deliveryId: string,
    message: string,
  ): Promise<{ message: string; message_id: string; in_reply_to: string | null }> {
    return firstValueFrom(
      this.http.post<{ message: string; message_id: string; in_reply_to: string | null }>(
        `${environment.apiUrl}/deliveries/${deliveryId}/follow-up`,
        { message },
      ),
    );
  }

  softDeleteDelivery(deliveryId: string): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${environment.apiUrl}/deliveries/${deliveryId}`));
  }
}
