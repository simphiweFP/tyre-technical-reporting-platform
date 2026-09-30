import { inject, Injectable } from '@angular/core';
import {
  CustomerRefreshResult,
  ReportReferenceData,
  ReportStore,
  ReportValidationResult,
} from '../../core/data/report.store';
import { ReportDeliveryService } from '../../core/delivery/report-delivery.service';
import {
  GeminiOcrResult,
  OptimizedImage,
  ReportIntelligenceService,
} from '../../core/media/report-intelligence.service';
import {
  DeliveryAttempt,
  ReportRecipient,
  TechnicalReport,
} from '../../shared/models/report.models';

@Injectable({ providedIn: 'root' })
export class ReportCaptureFacade {
  private readonly store = inject(ReportStore);
  private readonly delivery = inject(ReportDeliveryService);
  private readonly intelligence = inject(ReportIntelligenceService);

  createReport(): TechnicalReport {
    return this.store.create();
  }

  getLocalReport(id: string): TechnicalReport | undefined {
    return this.store.get(id);
  }

  loadReport(id: string): Promise<TechnicalReport> {
    return this.store.loadOne(id);
  }

  reports(): TechnicalReport[] {
    return this.store.reports();
  }

  save(report: TechnicalReport): void {
    this.store.save(report);
  }

  saveNow(report: TechnicalReport): Promise<void> {
    return this.store.saveNow(report);
  }

  validate(report: TechnicalReport, step: number): Promise<ReportValidationResult> {
    return this.store.validate(report, step);
  }

  referenceData(): Promise<ReportReferenceData> {
    return this.store.referenceData();
  }

  customerSuggestions(search: string): Promise<string[]> {
    return this.store.customerSuggestions(search);
  }

  refreshCustomers(): Promise<CustomerRefreshResult> {
    return this.store.refreshCustomers();
  }

  optimizeImage(file: File): Promise<OptimizedImage> {
    return this.intelligence.optimize(file);
  }

  analyseImage(blob: Blob, filename: string): Promise<GeminiOcrResult> {
    return this.intelligence.analyseImage(blob, filename);
  }

  uploadImage(
    reportId: string,
    category: string,
    blob: Blob,
    filename: string,
  ): ReturnType<ReportStore['uploadImage']> {
    return this.store.uploadImage(reportId, category, blob, filename);
  }

  deleteImage(reportId: string, imageId: string): Promise<void> {
    return this.store.deleteImage(reportId, imageId);
  }

  removeQueuedImage(reportId: string, category: string): Promise<void> {
    return this.store.removeQueuedImage(reportId, category);
  }

  recipients(report: TechnicalReport): Promise<ReportRecipient[]> {
    return this.delivery.recipients(true, report.branch, report.category);
  }

  deliver(report: TechnicalReport, recipientId: string): Promise<DeliveryAttempt> {
    return this.delivery.deliver(report, recipientId);
  }

  downloadPdf(report: TechnicalReport): Promise<void> {
    return this.intelligence.downloadPdf(report);
  }
}
