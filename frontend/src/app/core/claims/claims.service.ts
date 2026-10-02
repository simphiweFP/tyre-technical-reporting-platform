import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface Supplier {
  CardCode: string;
  CardName: string;
  CardType: string;
  VATNumber: string | null;
}
export interface ClaimOwner {
  id: string;
  full_name: string;
  email: string;
}
export interface AvailableReport {
  id: string;
  claim_reference: string;
  customer_name: string;
  branch: string;
}
export interface ClaimData {
  claim_date: string;
  tyre_size: string;
  supplier: string;
  supplier_code: string;
  damage: string;
  remaining_tread_depth: number | null;
  original_tread_depth: number | null;
  supplier_submitted_date: string | null;
  supplier_status: 'Under review' | 'Accepted' | 'Rejected';
  accepted_percentage: number | null;
  supplier_feedback_date: string | null;
  supplier_feedback_comments: string;
  customer_credit_percentage: number | null;
  credit_note_reference: string;
  customer_credit_date: string | null;
  supplier_offset_invoice: string;
  supplier_offset_date: string | null;
  customer_credit_amount: number | null;
  supplier_recovered_amount: number | null;
  currency: 'ZAR';
  instruction_supplier: string;
}
export interface Instruction {
  id: string;
  data: Record<string, unknown>;
  created_at: string;
  acknowledged_at: string | null;
}
export interface ClaimCase {
  id: string;
  report_id: string;
  claim_reference: string;
  customer_name: string;
  customer_invoice_number: string;
  branch: string;
  brand: string;
  tyre_size: string;
  pattern: string;
  serial_number: string;
  data: ClaimData;
  remaining_percentage: number | null;
  assigned_to: string;
  owner_name: string;
  owner_email: string;
  received_at: string;
  updated_at: string;
  workflow_status: 'Received' | 'In progress' | 'Closed';
  handover_notes: string;
  credit_outstanding: boolean;
  supplier_offset_outstanding: boolean;
  instructions: Instruction[];
}
export interface Scorecard {
  supplier: string;
  total_claims: number;
  acceptance_rate: number;
  rejection_rate: number;
  average_response_days: number | null;
  average_resolution_days: number | null;
  response_sample_size: number;
  resolution_sample_size: number;
  credit_value_recovered: number;
  missing_recovery_amounts: number;
}
export interface MetricRank {
  name: string;
  count: number;
}
export interface ClaimMetrics {
  scorecard: Scorecard[];
  total_claims: number;
  under_review: number;
  outstanding_supplier_offsets: number;
  credit_notes_not_passed: number;
  most_supplier: MetricRank[];
  least_supplier: MetricRank[];
  most_customer: MetricRank[];
  least_customer: MetricRank[];
}
export interface ClaimDelivery {
  id: string;
  document_type: string;
  status: string;
  recipient_email: string;
  error_message: string | null;
  created_at: string;
}
export interface ClaimActivity {
  id: string;
  action: string;
  actor: string;
  occurred_at: string;
}

@Injectable({ providedIn: 'root' })
export class ClaimsService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/claims`;
  list(filters: Record<string, string>, offset = 0) {
    return firstValueFrom(
      this.http.get<{ items: ClaimCase[]; total: number }>(this.base, {
        params: { ...filters, offset, limit: 100 },
      }),
    );
  }
  owners() {
    return firstValueFrom(this.http.get<ClaimOwner[]>(`${this.base}/owners`));
  }
  available() {
    return firstValueFrom(this.http.get<AvailableReport[]>(`${this.base}/available-reports`));
  }
  suppliers(search = '') {
    return firstValueFrom(
      this.http.get<{ items: Supplier[] }>(`${this.base}/suppliers`, { params: { search } }),
    );
  }
  get(id: string) {
    return firstValueFrom(this.http.get<ClaimCase>(`${this.base}/${id}`));
  }
  metrics(filters: Record<string, string>) {
    return firstValueFrom(this.http.get<ClaimMetrics>(`${this.base}/metrics`, { params: filters }));
  }
  handover(report_id: string, assigned_to: string, notes: string) {
    return firstValueFrom(
      this.http.post<ClaimCase>(`${this.base}/handover`, { report_id, assigned_to, notes }),
    );
  }
  update(item: ClaimCase, data: ClaimData, workflow_status: string) {
    return firstValueFrom(
      this.http.put<ClaimCase>(`${this.base}/${item.id}`, {
        data,
        workflow_status,
        expected_updated_at: item.updated_at,
      }),
    );
  }
  reassign(id: string, assigned_to: string, notes: string) {
    return firstValueFrom(
      this.http.post<ClaimCase>(`${this.base}/${id}/reassign`, { assigned_to, notes }),
    );
  }
  issue(id: string, supplier: string, notes: string) {
    return firstValueFrom(
      this.http.post<ClaimCase>(`${this.base}/${id}/instructions`, { supplier, notes }),
    );
  }
  receive(id: string, instruction: string) {
    return firstValueFrom(
      this.http.post<ClaimCase>(`${this.base}/${id}/instructions/${instruction}/receive`, {}),
    );
  }
  deliveries(claim: string) {
    return firstValueFrom(
      this.http.get<ClaimDelivery[]>(
        `${environment.apiUrl}/reports/${encodeURIComponent(claim)}/deliveries`,
      ),
    );
  }
  activity(id: string) {
    return firstValueFrom(this.http.get<ClaimActivity[]>(`${this.base}/${id}/activity`));
  }
  send(
    id: string,
    kind: string,
    recipient_email: string,
    cc: string[],
    body: string,
    instruction_id?: string,
  ) {
    return firstValueFrom(
      this.http.post<ClaimDelivery>(`${this.base}/${id}/documents/${kind}/send`, {
        recipient_email,
        cc,
        body,
        instruction_id,
      }),
    );
  }
  sendScorecard(
    filters: Record<string, string>,
    recipient_email: string,
    cc: string[],
    body: string,
  ) {
    return firstValueFrom(
      this.http.post<ClaimDelivery>(
        `${this.base}/scorecard/send`,
        { recipient_email, cc, body },
        { params: filters },
      ),
    );
  }
  import(file: File, assigned_to: string) {
    const body = new FormData();
    body.append('file', file);
    return firstValueFrom(
      this.http.post<{ imported: number; skipped: number; warnings: string[] }>(
        `${this.base}/import`,
        body,
        { params: { assigned_to } },
      ),
    );
  }
  async download(
    path: string,
    filename: string,
    filters: Record<string, string> = {},
  ): Promise<void> {
    const blob = await firstValueFrom(
      this.http.get(`${this.base}/${path}`, {
        params: new HttpParams({ fromObject: filters }),
        responseType: 'blob',
      }),
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
