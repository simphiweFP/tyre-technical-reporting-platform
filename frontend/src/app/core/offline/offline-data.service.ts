import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { TechnicalReport } from '../../shared/models/report.models';
import { AuthService } from '../auth/auth.service';
import type { ReportReferenceData } from '../data/report.store';

interface PendingReport {
  id: string;
  ownerId: string;
  report: TechnicalReport;
  expectedUpdatedAt: string | null;
  queuedAt: string;
  conflict: boolean;
  error: string;
}
interface PendingPhoto {
  key: string;
  ownerId: string;
  reportId: string;
  category: string;
  blob: Blob;
  filename: string;
  queuedAt: string;
  error: string;
}
interface PendingDeletion {
  key: string;
  ownerId: string;
  reportId: string;
  imageId: string;
  queuedAt: string;
  error: string;
}
interface PendingDelivery {
  key: string;
  ownerId: string;
  reportId: string;
  claimReference: string;
  recipientEmail: string;
  report: TechnicalReport;
  queuedAt: string;
  error: string;
}
interface MetaRecord { key: string; value: unknown; }
export interface OfflineStats {
  pendingReports: number;
  pendingPhotos: number;
  pendingDeletions: number;
  pendingDeliveries: number;
  conflicts: number;
  lastSyncedAt: string | null;
}
const EMPTY_STATS: OfflineStats = {
  pendingReports: 0,
  pendingPhotos: 0,
  pendingDeletions: 0,
  pendingDeliveries: 0,
  conflicts: 0,
  lastSyncedAt: null,
};

@Injectable({ providedIn: 'root' })
export class OfflineDataService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private dbPromise: Promise<IDBDatabase> | null = null;
  readonly online = signal(typeof navigator === 'undefined' ? true : navigator.onLine);
  readonly syncing = signal(false);
  readonly stats = signal<OfflineStats>(EMPTY_STATS);
  readonly lastDeliveryResult = signal<{
    claimReference: string;
    recipientEmail: string;
    status: string;
  } | null>(null);

  constructor() {
    if (typeof window !== 'undefined') {
      window.addEventListener('online', () => {
        this.online.set(true);
        void this.syncNow();
      });
      window.addEventListener('offline', () => this.online.set(false));
    }
    void this.refreshStats();
  }

  async queueReport(report: TechnicalReport, expectedUpdatedAt: string | null): Promise<void> {
    const existing = await this.getItem<PendingReport>('reports', report.id);
    const sanitized = {
      ...report,
      photos: report.photos.map((photo) =>
        photo.storageId ? photo : { ...photo, previewUrl: '' },
      ),
    };
    await this.put('reports', {
      id: report.id,
      ownerId: this.currentUserId(),
      report: sanitized,
      expectedUpdatedAt: existing?.expectedUpdatedAt ?? expectedUpdatedAt,
      queuedAt: existing?.queuedAt ?? new Date().toISOString(),
      conflict: existing?.conflict ?? false,
      error: existing?.error ?? '',
    } satisfies PendingReport);
    await this.refreshStats();
  }

  async removePendingReport(reportId: string): Promise<void> {
    await this.remove('reports', reportId);
    await this.refreshStats();
  }

  async loadReport(reportId: string): Promise<TechnicalReport | null> {
    const pending = await this.getItem<PendingReport>('reports', reportId);
    if (!pending || pending.ownerId !== this.currentUserId()) return null;
    const photos = await this.getAll<PendingPhoto>('photos');
    const queued = new Map(
      photos.filter((photo) => photo.reportId === reportId).map((photo) => [photo.category, photo]),
    );
    const rebuilt = await Promise.all(
      pending.report.photos.map(async (photo) => {
        if (photo.previewUrl) return photo;
        const local = queued.get(photo.category);
        return local ? { ...photo, previewUrl: await this.asDataUrl(local.blob) } : photo;
      }),
    );
    return { ...pending.report, photos: rebuilt };
  }

  async listPendingReports(): Promise<TechnicalReport[]> {
    const records = await this.getAll<PendingReport>('reports');
    const reports = await Promise.all(records.map((record) => this.loadReport(record.id)));
    return reports.filter((report): report is TechnicalReport => !!report);
  }

  async queuePhoto(reportId: string, category: string, blob: Blob, filename: string): Promise<void> {
    await this.put('photos', {
      key: `${reportId}:${category}`,
      ownerId: this.currentUserId(),
      reportId,
      category,
      blob,
      filename,
      queuedAt: new Date().toISOString(),
      error: '',
    } satisfies PendingPhoto);
    await this.refreshStats();
  }

  async removeQueuedPhoto(reportId: string, category: string): Promise<void> {
    await this.remove('photos', `${reportId}:${category}`);
    await this.refreshStats();
  }

  async queueImageDeletion(reportId: string, imageId: string): Promise<void> {
    await this.put('deletions', {
      key: `${reportId}:${imageId}`,
      ownerId: this.currentUserId(),
      reportId,
      imageId,
      queuedAt: new Date().toISOString(),
      error: '',
    } satisfies PendingDeletion);
    await this.refreshStats();
  }

  async cacheReferenceData(data: ReportReferenceData): Promise<void> {
    await this.put('meta', { key: this.userMetaKey('reference-data'), value: data } satisfies MetaRecord);
  }

  async referenceData(): Promise<ReportReferenceData | null> {
    const record = await this.getItem<MetaRecord>('meta', this.userMetaKey('reference-data'));
    return (record?.value as ReportReferenceData | undefined) ?? null;
  }

  async clearReferenceCache(): Promise<void> {
    await this.remove('meta', this.userMetaKey('reference-data'));
  }


  async queueDelivery(
    report: TechnicalReport,
    recipientEmail: string,
  ): Promise<void> {
    const normalizedEmail = recipientEmail.trim().toLowerCase();
    await this.put('deliveries', {
      key: `${report.id}:${normalizedEmail}`,
      ownerId: this.currentUserId(),
      reportId: report.id,
      claimReference: report.claimReference,
      recipientEmail: normalizedEmail,
      report,
      queuedAt: new Date().toISOString(),
      error: '',
    } satisfies PendingDelivery);
    await this.refreshStats();
  }

  async syncNow(): Promise<void> {
    if (!this.online() || this.syncing()) return;
    this.syncing.set(true);
    let syncedAnything = false;
    try {
      for (const pending of await this.getAll<PendingReport>('reports')) {
        if (pending.conflict) continue;
        try {
          await firstValueFrom(
            this.http.put(`${environment.apiUrl}/reports/records/${pending.id}`, {
              report: pending.report,
              expected_updated_at: pending.expectedUpdatedAt,
            }),
          );
          await this.remove('reports', pending.id);
          syncedAnything = true;
        } catch (error) {
          if (error instanceof HttpErrorResponse && error.status === 409) {
            pending.conflict = true;
            pending.error =
              typeof error.error?.detail === 'string'
                ? error.error.detail
                : 'The server copy changed while this device was offline.';
            await this.put('reports', pending);
            continue;
          }
          pending.error = 'Sync failed. The change remains stored on this device.';
          await this.put('reports', pending);
          if (error instanceof HttpErrorResponse && error.status === 0) break;
        }
      }

      const blocked = new Set(
        (await this.getAll<PendingReport>('reports')).map((record) => record.id),
      );

      for (const item of await this.getAll<PendingDeletion>('deletions')) {
        if (blocked.has(item.reportId)) continue;
        try {
          await firstValueFrom(
            this.http.delete(
              `${environment.apiUrl}/reports/records/${item.reportId}/images/${item.imageId}`,
            ),
          );
          await this.remove('deletions', item.key);
          syncedAnything = true;
        } catch (error) {
          if (error instanceof HttpErrorResponse && error.status === 404) {
            await this.remove('deletions', item.key);
            continue;
          }
          item.error = 'Image deletion is waiting for the next sync.';
          await this.put('deletions', item);
          if (error instanceof HttpErrorResponse && error.status === 0) break;
        }
      }

      for (const item of await this.getAll<PendingPhoto>('photos')) {
        if (blocked.has(item.reportId)) continue;
        const body = new FormData();
        body.append('image', item.blob, item.filename);
        try {
          await firstValueFrom(
            this.http.post(
              `${environment.apiUrl}/reports/records/${item.reportId}/images`,
              body,
              { params: { category: item.category } },
            ),
          );
          await this.remove('photos', item.key);
          syncedAnything = true;
        } catch (error) {
          item.error = 'Photo upload is waiting for the next sync.';
          await this.put('photos', item);
          if (error instanceof HttpErrorResponse && error.status === 0) break;
        }
      }

      const remainingReports = new Set(
        (await this.getAll<PendingReport>('reports')).map((record) => record.id),
      );
      const remainingPhotos = new Set(
        (await this.getAll<PendingPhoto>('photos')).map((record) => record.reportId),
      );

      for (const item of await this.getAll<PendingDelivery>('deliveries')) {
        if (remainingReports.has(item.reportId) || remainingPhotos.has(item.reportId)) continue;
        try {
          const result = await firstValueFrom(
            this.http.post<{ status: string }>(`${environment.apiUrl}/reports/deliver`, {
              recipient_email: item.recipientEmail,
              report: item.report,
              cc: [],
            }),
          );
          await this.remove('deliveries', item.key);
          this.lastDeliveryResult.set({
            claimReference: item.claimReference,
            recipientEmail: item.recipientEmail,
            status: result.status,
          });
          syncedAnything = true;
        } catch (error) {
          item.error = 'Email delivery is waiting for the next sync.';
          await this.put('deliveries', item);
          if (error instanceof HttpErrorResponse && error.status === 0) break;
        }
      }

      if (syncedAnything) {
        await this.put('meta', {
          key: this.userMetaKey('last-synced-at'),
          value: new Date().toISOString(),
        } satisfies MetaRecord);
      }
    } finally {
      this.syncing.set(false);
      await this.refreshStats();
    }
  }

  async refreshStats(): Promise<void> {
    try {
      const [reports, photos, deletions, deliveries, lastSync] = await Promise.all([
        this.getAll<PendingReport>('reports'),
        this.getAll<PendingPhoto>('photos'),
        this.getAll<PendingDeletion>('deletions'),
        this.getAll<PendingDelivery>('deliveries'),
        this.getItem<MetaRecord>('meta', this.userMetaKey('last-synced-at')),
      ]);
      this.stats.set({
        pendingReports: reports.length,
        pendingPhotos: photos.length,
        pendingDeletions: deletions.length,
        pendingDeliveries: deliveries.length,
        conflicts: reports.filter((report) => report.conflict).length,
        lastSyncedAt: typeof lastSync?.value === 'string' ? lastSync.value : null,
      });
    } catch {
      this.stats.set(EMPTY_STATS);
    }
  }

  private openDb(): Promise<IDBDatabase> {
    if (this.dbPromise) return this.dbPromise;
    this.dbPromise = new Promise((resolve, reject) => {
      if (typeof indexedDB === 'undefined') return reject(new Error('IndexedDB is unavailable'));
      const request = indexedDB.open('royal-tyres-offline', 2);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains('reports')) db.createObjectStore('reports', { keyPath: 'id' });
        if (!db.objectStoreNames.contains('photos')) db.createObjectStore('photos', { keyPath: 'key' });
        if (!db.objectStoreNames.contains('deletions')) db.createObjectStore('deletions', { keyPath: 'key' });
        if (!db.objectStoreNames.contains('deliveries')) db.createObjectStore('deliveries', { keyPath: 'key' });
        if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta', { keyPath: 'key' });
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    return this.dbPromise;
  }

  private async put(storeName: string, value: unknown): Promise<void> {
    const db = await this.openDb();
    const transaction = db.transaction(storeName, 'readwrite');
    transaction.objectStore(storeName).put(value);
    await this.transactionDone(transaction);
  }
  private async remove(storeName: string, key: IDBValidKey): Promise<void> {
    const db = await this.openDb();
    const transaction = db.transaction(storeName, 'readwrite');
    transaction.objectStore(storeName).delete(key);
    await this.transactionDone(transaction);
  }
  private async getItem<T>(storeName: string, key: IDBValidKey): Promise<T | undefined> {
    const db = await this.openDb();
    return this.request<T | undefined>(db.transaction(storeName, 'readonly').objectStore(storeName).get(key));
  }
  private async getAll<T>(storeName: string): Promise<T[]> {
    const db = await this.openDb();
    const values = await this.request<T[]>(
      db.transaction(storeName, 'readonly').objectStore(storeName).getAll(),
    );
    if (storeName === 'meta') return values;
    const ownerId = this.currentUserId();
    return values.filter(
      (value) => (value as { ownerId?: string }).ownerId === ownerId,
    );
  }

  private currentUserId(): string {
    return this.auth.user()?.id ?? '';
  }

  private userMetaKey(name: string): string {
    return `${this.currentUserId()}:${name}`;
  }
  private request<T>(request: IDBRequest<T>): Promise<T> {
    return new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }
  private transactionDone(transaction: IDBTransaction): Promise<void> {
    return new Promise((resolve, reject) => {
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
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
