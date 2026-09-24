import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ReportPhoto, TechnicalReport } from '../../shared/models/report.models';
import { OfflineDataService } from '../offline/offline-data.service';

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
  readonly offline = inject(OfflineDataService);
  private readonly state = signal<TechnicalReport[]>([]);
  private readonly serverUpdatedAt = new Map<string, string>();
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
    if (this.offline.online()) {
      void this.refresh();
    } else {
      void this.loadOfflineReports();
    }
    if (typeof window !== 'undefined') {
      window.addEventListener('online', () => {
        void this.offline.syncNow().then(() => this.refresh());
      });
    }
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
      if (!this.offline.online()) {
        await this.offline.queueReport(report, this.serverUpdatedAt.get(report.id) ?? null);
        return;
      }
      const response = await firstValueFrom(
        this.http.put<ServerReport>(`${environment.apiUrl}/reports/records/${report.id}`, {
          report,
        }),
      );
      this.serverUpdatedAt.set(report.id, response.updated_at);
      await this.offline.removePendingReport(report.id);
      this.updateLocal(this.mapReport(response));
    } catch (error) {
      if (!this.offline.online() || (error instanceof HttpErrorResponse && error.status === 0)) {
        await this.offline.queueReport(report, this.serverUpdatedAt.get(report.id) ?? null);
        return;
      }
      this.saveError.set('Changes could not be saved.');
      throw error;
    } finally {
      this.pendingSaves -= 1;
      this.saving.set(this.pendingSaves > 0);
    }
  }

  async refresh(search: ReportSearch = {}): Promise<void> {
    this.loading.set(true);
    if (!this.offline.online()) {
      await this.loadOfflineReports();
      this.loading.set(false);
      return;
    }
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
    if (!this.offline.online()) {
      const local = await this.offline.loadReport(reportId);
      if (!local) throw new Error('Report is not available offline');
      this.updateLocal(local);
      return local;
    }
    try {
      const response = await firstValueFrom(
        this.http.get<ServerReport>(`${environment.apiUrl}/reports/records/${reportId}`),
      );
      this.serverUpdatedAt.set(reportId, response.updated_at);
      const report = this.mapReport(response);
      this.updateLocal(report);
      await this.hydrateImages(reportId);
      return this.get(reportId) ?? report;
    } catch (error) {
      if (error instanceof HttpErrorResponse && error.status === 0) {
        const local = await this.offline.loadReport(reportId);
        if (local) {
          this.updateLocal(local);
          return local;
        }
      }
      throw error;
    }
  }

  async uploadImage(
    reportId: string,
    category: string,
    blob: Blob,
    filename: string,
  ): Promise<ServerImage | null> {
    if (!this.offline.online()) {
      await this.offline.queuePhoto(reportId, category, blob, filename);
      return null;
    }
    const body = new FormData();
    body.append('image', blob, filename);
    try {
      return await firstValueFrom(
        this.http.post<ServerImage>(
          `${environment.apiUrl}/reports/records/${reportId}/images`,
          body,
          { params: { category } },
        ),
      );
    } catch (error) {
      if (error instanceof HttpErrorResponse && error.status === 0) {
        await this.offline.queuePhoto(reportId, category, blob, filename);
        return null;
      }
      throw error;
    }
  }

  async deleteImage(reportId: string, imageId: string): Promise<void> {
    if (!this.offline.online()) {
      await this.offline.queueImageDeletion(reportId, imageId);
      return;
    }
    try {
      await firstValueFrom(
        this.http.delete<void>(
          `${environment.apiUrl}/reports/records/${reportId}/images/${imageId}`,
        ),
      );
    } catch (error) {
      if (error instanceof HttpErrorResponse && error.status === 0) {
        await this.offline.queueImageDeletion(reportId, imageId);
        return;
      }
      throw error;
    }
  }

  removeQueuedImage(reportId: string, category: string): Promise<void> {
    return this.offline.removeQueuedPhoto(reportId, category);
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

  async referenceData(): Promise<ReportReferenceData> {
    if (!this.offline.online()) {
      return (await this.offline.referenceData()) ?? this.referenceFallback();
    }
    try {
      const data = await firstValueFrom(
        this.http.get<ReportReferenceData>(`${environment.apiUrl}/reports/reference-data`),
      );
      await this.offline.cacheReferenceData(data);
      return data;
    } catch (error) {
      if (error instanceof HttpErrorResponse && error.status === 0) {
        return (await this.offline.referenceData()) ?? this.referenceFallback();
      }
      throw error;
    }
  }

  async validate(report: TechnicalReport, step: number): Promise<ReportValidationResult> {
    if (!this.offline.online()) return this.localValidation(report, step);
    try {
      return await firstValueFrom(
        this.http.post<ReportValidationResult>(`${environment.apiUrl}/reports/validate`, {
          report,
          step,
        }),
      );
    } catch (error) {
      if (error instanceof HttpErrorResponse && error.status === 0) {
        return this.localValidation(report, step);
      }
      throw error;
    }
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

  private async loadOfflineReports(): Promise<void> {
    const reports = await this.offline.listPendingReports();
    this.state.set(reports);
    this.total.set(reports.length);
    this.matchingTotal.set(reports.length);
    const counts: Record<string, number> = {};
    for (const report of reports) counts[report.status] = (counts[report.status] ?? 0) + 1;
    this.statusCounts.set(counts);
  }

  private localValidation(report: TechnicalReport, step: number): ReportValidationResult {
    const errors: Record<string, string> = {};
    if (step === 0 || step === 3) {
      if (!report.salesperson.trim()) errors['salesperson'] = 'Salesperson is required.';
      if (!report.customerName.trim()) errors['customerName'] = 'Customer name is required.';
      if (!report.branch.trim()) errors['branch'] = 'Branch selection is required.';
    }
    if (step === 1 || step === 3) {
      const captured = new Set(report.photos.map((photo) => photo.category));
      for (const [category, message] of [
        ['dot', 'DOT photo is required.'],
        ['serialNumber', 'Serial number photo is required.'],
        ['entireTyreDot', 'Entire tyre DOT-side photo is required.'],
        ['entireTyreOpposite', 'Entire tyre opposite-side photo is required.'],
        ['issue1', 'Issue photo is required.'],
        ['issue2', 'Second issue photo is required.'],
        ['bead1', 'Bead photo is required.'],
        ['bead2', 'Second bead photo is required.'],
        ['fullView', 'Full view photo is required.'],
        ['internalCarcass1', 'Internal carcass photo is required.'],
        ['internalCarcass2', 'Second internal carcass photo is required.'],
        ['treadDepth1', 'Tread depth photo is required.'],
        ['treadDepth2', 'Second tread depth photo is required.'],
        ['treadDepth3', 'Third tread depth photo is required.'],
        ['treadPattern', 'Tread pattern photo is required.'],
        ['vehicle', 'Vehicle photo is required.'],
      ] as const) {
        if (!captured.has(category)) errors[`photos.${category}`] = message;
      }
    }
    if (step === 2 || step === 3) {
      if (!report.brand.trim()) errors['brand'] = 'Brand is required.';
      if (!report.dot.trim()) errors['dot'] = 'DOT is required.';
      if (!report.serialNumber.trim()) errors['serialNumber'] = 'Serial number is required.';
    }
    return { valid: Object.keys(errors).length === 0, errors };
  }

  private referenceFallback(): ReportReferenceData {
    return {
      branches: [],
      customers: [],
      categories: ['Manufacturing', 'Road hazard', 'Service related'],
      brands: ['Bridgestone', 'Continental', 'Dunlop', 'Goodyear', 'Hankook', 'Michelin'],
      patterns: [],
      tyre_positions: ['Front left', 'Front right', 'Rear left', 'Rear right', 'Spare'],
    };
  }

  private mapReport(item: ServerReport): TechnicalReport {
    this.serverUpdatedAt.set(item.id, item.updated_at);
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
