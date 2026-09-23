import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface SystemSettings {
  company_name: string;
  ocr_confidence_threshold: number;
  pdf_template: string;
  offline_sync_enabled: boolean;
  offline_sync_minutes: number;
  smtp_server: string;
}
export interface AuditEvent {
  id: string;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  details: Record<string, unknown>;
  occurred_at: string;
}
export interface OperationsStatus {
  status: string;
  database: string;
  file_storage: string;
  delivery_worker: string;
  worker_last_seen_at: string | null;
  pending_deliveries: number;
  retrying_deliveries: number;
  failed_deliveries: number;
  oldest_pending_at: string | null;
}

@Injectable({ providedIn: 'root' })
export class SystemAdminService {
  private readonly http = inject(HttpClient);
  settings() {
    return firstValueFrom(this.http.get<SystemSettings>(`${environment.apiUrl}/admin/settings`));
  }
  saveSettings(value: SystemSettings) {
    return firstValueFrom(
      this.http.put<SystemSettings>(`${environment.apiUrl}/admin/settings`, value),
    );
  }
  auditEvents(query = '', days = 7) {
    return firstValueFrom(
      this.http.get<{ items: AuditEvent[]; total: number }>(
        `${environment.apiUrl}/admin/audit-events`,
        { params: { query, days } },
      ),
    );
  }
  operations() {
    return firstValueFrom(
      this.http.get<OperationsStatus>(`${environment.apiUrl}/admin/operations`),
    );
  }
}
