import { HttpClient, HttpParams } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ReportPhoto, TechnicalReport } from '../../shared/models/report.models';

interface ServerImage {
  id: string;
  category: string;
  original_name: string;
  content_type: string;
  sha256: string;
  byte_size: number;
  captured_at: string;
}
interface ServerReport {
  id: string;
  report: Omit<TechnicalReport, 'photos'> & { photos: ServerImage[] };
  archived: boolean;
  created_at: string;
  updated_at: string;
}
interface ReportListResponse {
  items: ServerReport[];
  total: number;
  matching_total: number;
  status_counts: Record<string, number>;
}
export interface ReportAnalytics {
  total: number;
  drafts: number;
  completed: number;
  email_failed: number;
  by_status: Record<string, number>;
  by_branch: Record<string, number>;
  by_brand: Record<string, number>;
  by_category: Record<string, number>;
  by_month: Record<string, number>;
}
export interface ReportReferenceData {
  branches: { value: string; label: string }[];
  customers: string[];
  categories: string[];
  brands: string[];
  patterns: string[];
  tyre_positions: string[];
}
export interface ReportValidationResult {
  valid: boolean;
  errors: Record<string, string>;
}

export interface ReportSearch {
  query?: string;
  status?: string;
  branch?: string;
  dateFrom?: string;
  dateTo?: string;
  archived?: boolean;
  offset?: number;
  limit?: number;
}

@Injectable({ providedIn: 'root' })
export class ReportStore {
  private readonly http = inject(HttpClient);
  private readonly state = signal<TechnicalReport[]>([]);
  readonly reports = this.state.asReadonly();
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly saveError = signal('');
  readonly total = signal(0);
  readonly matchingTotal = signal(0);
  readonly statusCounts = signal<Record<string, number>>({});
  readonly drafts = computed(() => this.state().filter((report) => report.status === 'Draft'));
  private pendingSaves = 0;

  constructor() {
    void this.refresh();
  }

  get(id: string): TechnicalReport | undefined {
    return this.state().find((report) => report.id === id);
  }

  save(report: TechnicalReport): void {
    this.updateLocal(report);
    void this.saveNow(report).catch(() => undefined);
  }

  async saveNow(report: TechnicalReport): Promise<void> {
    this.pendingSaves += 1;
    this.saving.set(true);
    this.saveError.set('');
    this.updateLocal(report);
    try {
      const response = await firstValueFrom(
        this.http.put<ServerReport>(`${environment.apiUrl}/reports/records/${report.id}`, {
          report,
        }),
      );
      this.updateLocal(this.mapReport(response));
    } catch (error) {
      this.saveError.set('Changes are not saved to the server. Check your connection.');
      throw error;
    } finally {
      this.pendingSaves -= 1;
      this.saving.set(this.pendingSaves > 0);
    }
  }

  async refresh(search: ReportSearch = {}): Promise<void> {
    this.loading.set(true);
    try {
      let params = new HttpParams()
        .set('query', search.query ?? '')
        .set('report_status', search.status ?? '')
        .set('branch', search.branch ?? '')
        .set('include_archived', false)
        .set('archived_only', search.archived ?? false)
        .set('offset', search.offset ?? 0)
        .set('limit', search.limit ?? 20);
      if (search.dateFrom) params = params.set('date_from', search.dateFrom);
      if (search.dateTo) params = params.set('date_to', search.dateTo);
      const response = await firstValueFrom(
        this.http.get<ReportListResponse>(`${environment.apiUrl}/reports/records`, {
          params,
        }),
      );
      this.state.set(response.items.map((item) => this.mapReport(item)));
      this.total.set(response.total);
      this.matchingTotal.set(response.matching_total);
      this.statusCounts.set(response.status_counts);
    } catch {
      this.state.set([]);
      this.total.set(0);
      this.matchingTotal.set(0);
      this.statusCounts.set({});
    } finally {
      this.loading.set(false);
    }
  }

  async hydrateImages(reportId: string): Promise<void> {
    const report = this.get(reportId);
    if (!report) return;
    const photos = await Promise.all(
      report.photos.map(async (photo) => {
        if (photo.previewUrl || !photo.storageId) return photo;
        const blob = await firstValueFrom(
          this.http.get(
            `${environment.apiUrl}/reports/records/${reportId}/images/${photo.storageId}`,
            { responseType: 'blob' },
          ),
        );
        return { ...photo, previewUrl: await this.asDataUrl(blob) };
      }),
    );
    this.updateLocal({ ...report, photos });
  }

  async loadOne(reportId: string): Promise<TechnicalReport> {
    const response = await firstValueFrom(
      this.http.get<ServerReport>(`${environment.apiUrl}/reports/records/${reportId}`),
    );
    const report = this.mapReport(response);
    this.updateLocal(report);
    await this.hydrateImages(reportId);
    return this.get(reportId) ?? report;
  }

  async uploadImage(
    reportId: string,
    category: string,
    blob: Blob,
    filename: string,
  ): Promise<ServerImage> {
    const body = new FormData();
    body.append('image', blob, filename);
    return firstValueFrom(
      this.http.post<ServerImage>(
        `${environment.apiUrl}/reports/records/${reportId}/images`,
        body,
        { params: { category } },
      ),
    );
  }

  async deleteImage(reportId: string, imageId: string): Promise<void> {
    await firstValueFrom(
      this.http.delete<void>(`${environment.apiUrl}/reports/records/${reportId}/images/${imageId}`),
    );
  }

  async archive(id: string): Promise<void> {
    await firstValueFrom(
      this.http.post<void>(`${environment.apiUrl}/reports/records/${id}/archive`, null),
    );
    this.state.update((items) => items.filter((item) => item.id !== id));
  }

  analytics(): Promise<ReportAnalytics> {
    return firstValueFrom(
      this.http.get<ReportAnalytics>(`${environment.apiUrl}/reports/analytics/summary`),
    );
  }

  referenceData(): Promise<ReportReferenceData> {
    return firstValueFrom(
      this.http.get<ReportReferenceData>(`${environment.apiUrl}/reports/reference-data`),
    );
  }

  validate(report: TechnicalReport, step: number): Promise<ReportValidationResult> {
    return firstValueFrom(
      this.http.post<ReportValidationResult>(`${environment.apiUrl}/reports/validate`, {
        report,
        step,
      }),
    );
  }

  create(): TechnicalReport {
    const now = new Date().toISOString();
    return {
      id: crypto.randomUUID(),
      claimReference: `TR-${new Date().getFullYear()}-${crypto.randomUUID().slice(0, 6).toUpperCase()}`,
      createdAt: now,
      updatedAt: now,
      status: 'Draft',
      branch: '',
      internalExternal: 'Internal',
      salesperson: '',
      customerName: '',
      customerInvoiceNumber: '',
      category: '',
      inspectedLocation: '',
      returnedWithRim: null,
      fittedLoose: '',
      brand: '',
      rimSize: '',
      pattern: '',
      dot: '',
      serialNumber: '',
      claimCode: '',
      remainingTreadDepth: '',
      inspectedPressure: '',
      tyreMileage: '',
      tyrePosition: '',
      natureOfRepair: '',
      vehicleMakeModel: '',
      vehicleMileage: '',
      goodsTransported: '',
      notes: '',
      photos: [],
    };
  }

  private mapReport(item: ServerReport): TechnicalReport {
    const photos: ReportPhoto[] = (item.report.photos ?? []).map((photo) => ({
      category: photo.category,
      name: photo.original_name,
      label: photo.category,
      previewUrl: '',
      capturedAt: photo.captured_at,
      mimeType: photo.content_type,
      byteSize: photo.byte_size,
      sha256: photo.sha256,
      storageId: photo.id,
    }));
    return {
      ...item.report,
      id: item.id,
      createdAt: item.created_at,
      updatedAt: item.updated_at,
      photos,
    };
  }

  private updateLocal(report: TechnicalReport): void {
    this.state.update((items) =>
      items.some((item) => item.id === report.id)
        ? items.map((item) => (item.id === report.id ? report : item))
        : [report, ...items],
    );
  }

  private asDataUrl(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });
  }
}
