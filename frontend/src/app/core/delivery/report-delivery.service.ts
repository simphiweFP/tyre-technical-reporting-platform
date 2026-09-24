import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  DeliveryAttempt,
  ReportRecipient,
  TechnicalReport,
} from '../../shared/models/report.models';

export interface RecipientInput {
  company: string;
  contact_name: string;
  email: string;
  default_cc: string[];
  branch_code: string;
  category: string;
  escalation_enabled: boolean;
}

@Injectable({ providedIn: 'root' })
export class ReportDeliveryService {
  private readonly http = inject(HttpClient);

  recipients(activeOnly = true, branch = '', category = ''): Promise<ReportRecipient[]> {
    const params = new HttpParams()
      .set('active_only', activeOnly)
      .set('branch', branch)
      .set('category', category);
    return firstValueFrom(
      this.http.get<ReportRecipient[]>(`${environment.apiUrl}/recipients`, { params }),
    );
  }

  createRecipient(input: RecipientInput): Promise<ReportRecipient> {
    return firstValueFrom(
      this.http.post<ReportRecipient>(`${environment.apiUrl}/recipients`, input),
    );
  }

  setRecipientStatus(id: string, active: boolean): Promise<ReportRecipient> {
    const params = new HttpParams().set('is_active', active);
    return firstValueFrom(
      this.http.patch<ReportRecipient>(`${environment.apiUrl}/recipients/${id}/status`, null, {
        params,
      }),
    );
  }
  updateRecipient(
    id: string,
    input: RecipientInput & { is_active: boolean },
  ): Promise<ReportRecipient> {
    return firstValueFrom(
      this.http.put<ReportRecipient>(`${environment.apiUrl}/recipients/${id}`, input),
    );
  }
  testRecipient(id: string): Promise<{ message: string }> {
    return firstValueFrom(
      this.http.post<{ message: string }>(`${environment.apiUrl}/recipients/${id}/test`, null),
    );
  }
  deliveries(query = '', status = ''): Promise<{ items: DeliveryAttempt[]; total: number }> {
    return firstValueFrom(
      this.http.get<{ items: DeliveryAttempt[]; total: number }>(
        `${environment.apiUrl}/deliveries`,
        { params: { query, delivery_status: status } },
      ),
    );
  }

  deliver(report: TechnicalReport, recipientId: string): Promise<DeliveryAttempt> {
    return firstValueFrom(
      this.http.post<DeliveryAttempt>(`${environment.apiUrl}/reports/deliver`, {
        recipient_id: recipientId,
        report,
        cc: [],
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
}
