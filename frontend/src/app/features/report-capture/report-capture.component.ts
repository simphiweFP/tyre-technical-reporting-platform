import { Component, computed, inject, OnDestroy, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { debounceTime, Subject, takeUntil } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { ReportReferenceData, ReportStore } from '../../core/data/report.store';
import { ReportDeliveryService } from '../../core/delivery/report-delivery.service';
import { ReportIntelligenceService } from '../../core/media/report-intelligence.service';
import { OfflineDataService } from '../../core/offline/offline-data.service';
import {
  PHOTO_CATEGORIES,
  ReportPhoto,
  ReportRecipient,
  TechnicalReport,
} from '../../shared/models/report.models';
@Component({
  selector: 'app-report-capture',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './report-capture.component.html',
  styleUrl: './report-capture.component.scss',
})
export class ReportCaptureComponent implements OnDestroy {
  private readonly fb = inject(FormBuilder);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly store = inject(ReportStore);
  private readonly auth = inject(AuthService);
  private readonly intelligence = inject(ReportIntelligenceService);
  private readonly delivery = inject(ReportDeliveryService);
  readonly offline = inject(OfflineDataService);
  private readonly destroy$ = new Subject<void>();
  readonly step = signal(0);
  readonly captureMessage = signal('');
  readonly readonlyView = computed(() => this.auth.hasRole('viewer'));
  readonly recipients = signal<ReportRecipient[]>([]);
  readonly selectedRecipient = signal('');
  readonly confirmed = signal(false);
  readonly submitting = signal(false);
  readonly pdfBusy = signal(false);
  readonly previewMode = signal(false);
  readonly successMode = signal(false);
  readonly deliveryStatus = signal('Pending');
  readonly deliveryEmail = signal('');
  readonly validationErrors = signal<Record<string, string>>({});
  readonly stepLabels = ['Report details', 'Take photos', 'Tyre & vehicle', 'Review'];
  readonly photoCategories = PHOTO_CATEGORIES;
  readonly requiredCount = PHOTO_CATEGORIES.filter((p) => p.required).length;
  readonly report = signal<TechnicalReport>(this.loadReport());
  readonly referenceData = signal<ReportReferenceData>({
    branches: [],
    customers: [],
    categories: [],
    brands: [],
    patterns: [],
    tyre_positions: [],
  });
  readonly form = this.fb.nonNullable.group({
    internalExternal: [this.report().internalExternal],
    branch: [this.report().branch],
    salesperson: [this.report().salesperson],
    customerName: [this.report().customerName],
    customerInvoiceNumber: [this.report().customerInvoiceNumber],
    category: [this.report().category],
    inspectedLocation: [this.report().inspectedLocation],
    returnedWithRim: [this.report().returnedWithRim],
    fittedLoose: [this.report().fittedLoose],
    brand: [this.report().brand],
    rimSize: [this.report().rimSize],
    pattern: [this.report().pattern],
    dot: [this.report().dot],
    serialNumber: [this.report().serialNumber],
    claimCode: [this.report().claimCode],
    remainingTreadDepth: [this.report().remainingTreadDepth],
    inspectedPressure: [this.report().inspectedPressure],
    tyreMileage: [this.report().tyreMileage],
    tyrePosition: [this.report().tyrePosition],
    natureOfRepair: [this.report().natureOfRepair],
    vehicleMakeModel: [this.report().vehicleMakeModel],
    vehicleMileage: [this.report().vehicleMileage],
    goodsTransported: [this.report().goodsTransported],
    notes: [this.report().notes],
  });
  readonly photoCount = computed(
    () =>
      this.report().photos.filter(
        (photo) => PHOTO_CATEGORIES.find((p) => p.key === photo.category)?.required,
      ).length,
  );
  readonly duplicateWarning = computed(() => {
    const current = this.form.getRawValue();
    const duplicate = this.store
      .reports()
      .find(
        (item) =>
          item.id !== this.report().id &&
          ((current.customerInvoiceNumber &&
            item.customerInvoiceNumber === current.customerInvoiceNumber) ||
            (current.serialNumber && item.serialNumber === current.serialNumber)),
      );
    return duplicate
      ? `Possible duplicate of ${duplicate.claimReference}. Verify before sending.`
      : '';
  });
  constructor() {
    if (this.readonlyView()) this.form.disable({ emitEvent: false });
    this.form.controls.salesperson.setValue(this.auth.user()?.full_name ?? '', {
      emitEvent: false,
    });
    this.form.valueChanges
      .pipe(debounceTime(650), takeUntil(this.destroy$))
      .subscribe(() => this.persist());
    void this.loadDeliveryData();
    void this.loadReferenceData();
    if (this.route.snapshot.paramMap.get('id')) void this.loadServerReport();
    else this.persist();
  }
  ngOnDestroy(): void {
    if (!this.readonlyView()) this.persist();
    this.destroy$.next();
    this.destroy$.complete();
  }
  async goTo(value: number): Promise<void> {
    if (value > this.step()) {
      if (value > this.step() + 1 || !(await this.validateStep(this.step()))) return;
    }
    this.step.set(value);
    if (value === 3) void this.loadDeliveryData();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  async next(): Promise<void> {
    if (this.step() < 3) {
      await this.goTo(this.step() + 1);
      return;
    }
    if (!this.confirmed() || !(await this.validateStep(3))) return;
    this.captureMessage.set('');
    this.submitting.set(true);
    try {
      const ready = { ...this.currentReport(), status: 'Ready to Submit' as const };
      this.report.set(ready);
      await this.store.saveNow(ready);
      await this.loadDeliveryData();
      this.previewMode.set(true);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch {
      this.captureMessage.set('The report could not be saved to the API. Check the connection.');
    } finally {
      this.submitting.set(false);
    }
  }
  previous(): void {
    if (this.step() > 0) this.goTo(this.step() - 1);
  }
  async saveDraft(): Promise<void> {
    const updated = this.currentReport();
    this.report.set(updated);
    await this.store.saveNow(updated);
  }
  photoFor(category: string): ReportPhoto | undefined {
    return this.report().photos.find((p) => p.category === category);
  }
  async capture(event: Event, category: string): Promise<void> {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    input.value = '';
    this.captureMessage.set('');
    try {
      const optimized = await this.intelligence.optimize(file);
      const duplicate = this.report().photos.find(
        (photo) => photo.sha256 === optimized.sha256 && photo.category !== category,
      );
      if (duplicate) {
        this.captureMessage.set(
          `That image is already used for ${duplicate.label}. Capture a different view.`,
        );
        return;
      }
      const categoryDetails = PHOTO_CATEGORIES.find((item) => item.key === category);
      const photo: ReportPhoto = {
        category,
        name: file.name,
        label: categoryDetails?.label ?? category,
        previewUrl: optimized.previewUrl,
        capturedAt: new Date().toISOString(),
        mimeType: optimized.blob.type,
        byteSize: optimized.blob.size,
        sha256: optimized.sha256,
      };
      this.report.update((r) => ({
        ...r,
        photos: [...r.photos.filter((p) => p.category !== category), photo],
      }));
      const current = {
        ...this.report(),
        ...this.form.getRawValue(),
        updatedAt: new Date().toISOString(),
      };
      await this.store.saveNow(current);
      const stored = await this.store.uploadImage(current.id, category, optimized.blob, file.name);
      if (stored) {
        this.report.update((r) => ({
          ...r,
          photos: r.photos.map((item) =>
            item.category === category ? { ...item, storageId: stored.id } : item,
          ),
        }));
      } else {
        this.captureMessage.set('Photo saved on this device and will upload when you are online.');
      }
      this.persist();
    } catch {
      this.captureMessage.set('The image could not be processed. Try another photo.');
    }
  }
  async removePhoto(category: string): Promise<void> {
    const photo = this.photoFor(category);
    if (photo?.storageId) {
      await this.store.deleteImage(this.report().id, photo.storageId);
    } else {
      await this.store.removeQueuedImage(this.report().id, category);
    }
    this.report.update((r) => ({ ...r, photos: r.photos.filter((p) => p.category !== category) }));
    this.persist();
  }
  photoIcon(category: string): string {
    if (category.startsWith('tread')) return '▥';
    if (category === 'vehicle') return '▰';
    if (category.startsWith('issue')) return '◉';
    return '◌';
  }
  reviewRows(): { label: string; value: string }[] {
    const values = this.form.getRawValue();
    return [
      { label: 'Brand', value: values.brand || 'Not captured' },
      { label: 'Rim size', value: values.rimSize || 'Not captured' },
      { label: 'DOT', value: values.dot || 'Not captured' },
      { label: 'Serial number', value: values.serialNumber || 'Not captured' },
    ];
  }
  toggleConfirmed(event: Event): void {
    this.confirmed.set((event.target as HTMLInputElement).checked);
  }
  async sendReport(): Promise<void> {
    if (!this.offline.online()) {
      this.captureMessage.set('Sending is unavailable offline. The report is saved locally and will sync when you reconnect.');
      return;
    }
    if (!(await this.validateStep(3)) || !this.selectedRecipient()) return;
    const current = this.currentReport();
    this.report.set(current);
    await this.store.saveNow(current);
    const result = await this.delivery.deliver(this.report(), this.selectedRecipient());
    const updated = {
      ...this.report(),
      status: result.status === 'Sent' ? ('Email Sent' as const) : ('Submitted' as const),
    };
    this.report.set(updated);
    await this.store.saveNow(updated);
    this.deliveryStatus.set(result.status);
    this.deliveryEmail.set(result.recipient_email);
  }
  async downloadPdf(): Promise<void> {
    if (!this.offline.online()) {
      this.captureMessage.set('PDF generation requires the API. Reconnect first; your offline changes are safe.');
      return;
    }
    if (!(await this.validateStep(3))) return;
    this.pdfBusy.set(true);
    this.captureMessage.set('');
    try {
      const current = this.currentReport();
      this.report.set(current);
      await this.store.saveNow(current);
      await this.intelligence.downloadPdf(current);
    } catch {
      this.captureMessage.set('PDF generation failed. Check the API connection and try again.');
    } finally {
      this.pdfBusy.set(false);
    }
  }
  editReport(): void {
    this.previewMode.set(false);
    this.step.set(3);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  async sendFromPreview(): Promise<void> {
    if (!this.selectedRecipient()) {
      this.captureMessage.set(
        'No active report recipient is configured for this branch and category. Contact an administrator.',
      );
      return;
    }
    this.submitting.set(true);
    this.captureMessage.set('');
    try {
      await this.sendReport();
      this.previewMode.set(false);
      this.successMode.set(true);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch {
      this.captureMessage.set(
        'The report could not be sent. Check the API connection and try again.',
      );
    } finally {
      this.submitting.set(false);
    }
  }
  startAnotherReport(): void {
    void this.router.navigate(['/reports/new']).then(() => window.location.reload());
  }
  private async loadDeliveryData(): Promise<void> {
    try {
      const current = this.currentReport();
      const recipients = await this.delivery.recipients(true, current.branch, current.category);
      this.recipients.set(recipients);
      if (!this.selectedRecipient() && recipients.length) {
        this.selectedRecipient.set(recipients[0].id);
      }
    } catch {
      this.recipients.set([]);
      this.captureMessage.set('Delivery contacts are temporarily unavailable.');
    }
  }
  private async loadReferenceData(): Promise<void> {
    try {
      const data = await this.store.referenceData();
      this.referenceData.set(data);
      const current = this.form.controls.branch.value;
      const matching = data.branches.find(
        (branch) =>
          branch.value === current || branch.label.toLowerCase() === current.toLowerCase(),
      );
      if (matching && matching.value !== current) {
        this.form.controls.branch.setValue(matching.value, { emitEvent: false });
        this.persist();
      }
    } catch {
      this.captureMessage.set('Technical report dropdown data is temporarily unavailable.');
    }
  }
  private async validateStep(step: number): Promise<boolean> {
    this.persist();
    try {
      const result = await this.store.validate(this.currentReport(), step);
      this.validationErrors.set(result.errors);
      if (result.valid) {
        this.captureMessage.set('');
        return true;
      }
      this.captureMessage.set('Correct the highlighted fields before continuing.');
      if (step === 3) {
        const keys = Object.keys(result.errors);
        if (keys.some((key) => ['salesperson', 'customerName', 'branch'].includes(key))) {
          this.step.set(0);
        } else if (keys.some((key) => key.startsWith('photos.'))) {
          this.step.set(1);
        } else {
          this.step.set(2);
        }
        this.previewMode.set(false);
      }
      return false;
    } catch {
      this.captureMessage.set('The API could not validate this report. Try again.');
      return false;
    }
  }
  private loadReport(): TechnicalReport {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) return this.store.create();
    return this.store.get(id) ?? { ...this.store.create(), id };
  }
  private async loadServerReport(): Promise<void> {
    try {
      const loaded = await this.store.loadOne(this.report().id);
      this.report.set(loaded);
      this.form.patchValue(loaded, { emitEvent: false });
      this.form.controls.salesperson.setValue(this.auth.user()?.full_name ?? '', {
        emitEvent: false,
      });
    } catch {
      this.captureMessage.set('This report could not be loaded from the server.');
    }
  }
  private persist(): void {
    if (this.readonlyView()) return;
    const value = this.form.getRawValue();
    const updated = { ...this.report(), ...value, updatedAt: new Date().toISOString() };
    this.report.set(updated);
    try {
      this.store.save(updated);
    } catch {}
  }
  private currentReport(): TechnicalReport {
    return {
      ...this.report(),
      ...this.form.getRawValue(),
      updatedAt: new Date().toISOString(),
    };
  }
}
