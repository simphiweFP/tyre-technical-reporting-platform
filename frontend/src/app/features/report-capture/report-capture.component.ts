import { Component, computed, effect, inject, OnDestroy, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { debounceTime, Subject, takeUntil } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { ReportReferenceData } from '../../core/data/report.store';
import { OfflineDataService } from '../../core/offline/offline-data.service';
import { SweetAlertService } from '../../core/ui/sweet-alert.service';
import { ReportCaptureFacade } from './report-capture.facade';
import {
  DeliveryAttempt,
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
  private readonly workflow = inject(ReportCaptureFacade);
  private readonly auth = inject(AuthService);
  readonly offline = inject(OfflineDataService);
  private readonly alerts = inject(SweetAlertService);
  private readonly destroy$ = new Subject<void>();
  private readonly customerSearch$ = new Subject<string>();
  readonly step = signal(0);
  readonly captureMessage = signal('');
  readonly customerMatches = signal<string[]>([]);
  readonly customerLookupBusy = signal(false);
  readonly customerRefreshBusy = signal(false);
  readonly customerRefreshMessage = signal('');
  readonly customerDropdownOpen = signal(false);
  readonly tyrePositionModalOpen = signal(false);
  readonly tyreVehicleType = signal<'Car' | 'Horse' | 'Trailer'>('Horse');
  readonly readonlyView = computed(() => this.auth.hasRole('viewer'));
  readonly recipients = signal<ReportRecipient[]>([]);
  readonly selectedRecipient = signal('');
  readonly hasSelectedRecipient = computed(() =>
    this.recipients().some((recipient) => recipient.id === this.selectedRecipient()),
  );
  readonly confirmed = signal(false);
  readonly submitting = signal(false);
  readonly pdfBusy = signal(false);
  readonly previewMode = signal(false);
  readonly successMode = signal(false);
  readonly deliveryStatus = signal('Pending');
  readonly deliveryEmail = signal('');
  readonly validationErrors = signal<Record<string, string>>({});
  readonly stepLabels = ['Report details', 'Take photos', 'Tyre & vehicle'];
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
    const duplicate = this.workflow
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
    effect(() => {
      const result = this.offline.lastDeliveryResult();
      if (!result || result.claimReference !== this.report().claimReference) return;
      this.deliveryStatus.set(result.status);
      this.deliveryEmail.set(result.recipientEmail);
      if (result.status === 'Sent') {
        this.report.update((report) => ({ ...report, status: 'Email Sent' }));
      }
    });

    if (this.readonlyView()) this.form.disable({ emitEvent: false });
    this.form.controls.salesperson.setValue(this.auth.user()?.full_name ?? '', {
      emitEvent: false,
    });
    this.form.valueChanges
      .pipe(takeUntil(this.destroy$))
      .subscribe(() => this.clearResolvedValidationErrors());

    this.form.valueChanges
      .pipe(debounceTime(650), takeUntil(this.destroy$))
      .subscribe(() => this.persist());
    this.customerSearch$
      .pipe(debounceTime(400), takeUntil(this.destroy$))
      .subscribe((term) => void this.loadCustomerSuggestions(term));
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
    this.step.set(Math.max(0, Math.min(value, 2)));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  async next(): Promise<void> {
    if (this.step() < 2) {
      await this.goTo(this.step() + 1);
      return;
    }

    if (!(await this.validateStep(3))) return;

    this.captureMessage.set('');
    this.submitting.set(true);
    try {
      const ready = { ...this.currentReport(), status: 'Ready to Submit' as const };
      this.report.set(ready);
      await this.workflow.saveNow(ready);
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
  onCustomerSearch(value: string): void {
    const term = value.trim();

    if (term.length < 3) {
      this.customerMatches.set([]);
      this.customerDropdownOpen.set(false);
      return;
    }

    const normalized = term.toLowerCase();
    const localMatches = this.referenceData()
      .customers
      .filter((customer) => customer.toLowerCase().includes(normalized))
      .slice(0, 20);

    if (localMatches.length) {
      this.customerMatches.set(localMatches);
      this.customerDropdownOpen.set(true);
      return;
    }

    this.customerMatches.set([]);
    this.customerDropdownOpen.set(true);
    this.customerSearch$.next(term);
  }

  selectCustomer(customer: string): void {
    this.form.controls.customerName.setValue(customer);
    this.customerMatches.set([]);
    this.customerDropdownOpen.set(false);
    this.customerRefreshMessage.set('');
  }

  async refreshCustomers(): Promise<void> {
    if (this.customerRefreshBusy()) return;
    this.alerts.loading('Refreshing customers…', 'Checking the latest SAP customer list.');

    const term = this.form.controls.customerName.value.trim();
    this.customerRefreshBusy.set(true);
    this.customerRefreshMessage.set('');

    try {
      const result = await this.workflow.refreshCustomers();
      const data = await this.workflow.referenceData();
      this.referenceData.set(data);

      const matches = term
        ? data.customers
            .filter((customer) => customer.toLowerCase().includes(term.toLowerCase()))
            .slice(0, 20)
        : [];

      this.customerMatches.set(matches);
      this.customerDropdownOpen.set(Boolean(term));

      const sources = result.companyCounts
        ? Object.entries(result.companyCounts)
            .map(([company, count]) => `${company}: ${count}`)
            .join(', ')
        : '';

      if (result.checked === 0) {
        this.customerRefreshMessage.set(
          'SAP returned no customer records. Check the middleware /sap/customers endpoint and RTC/RVS company values.',
        );
      } else if (matches.length) {
        this.customerRefreshMessage.set(
          result.added
            ? `Customer list refreshed from SAP (${sources}). ${result.added} new customer${result.added === 1 ? '' : 's'} added.`
            : `Customer list refreshed from SAP (${sources}). No new customers were added.`,
        );
      } else {
        this.customerRefreshMessage.set(
          result.added
            ? `SAP refresh complete (${sources}). ${result.added} new customer${result.added === 1 ? '' : 's'} added, but no match was found. You can keep typing the customer name.`
            : `SAP refresh complete (${sources}). No matching customer was found, so you can keep typing the customer name.`,
        );
      }
    } catch {
      this.customerRefreshMessage.set(
        'Customer refresh could not reach SAP. You can still enter the customer name manually.',
      );
    } finally {
      this.alerts.close();
      this.customerRefreshBusy.set(false);
    }
  }

  closeCustomerDropdown(): void {
    window.setTimeout(() => this.customerDropdownOpen.set(false), 150);
  }

  async saveDraft(): Promise<void> {
    const updated = this.currentReport();
    this.report.set(updated);
    this.alerts.loading('Saving draft…', 'Keeping your current report progress safe.');
    try {
      await this.workflow.saveNow(updated);
      this.alerts.close();
      await this.alerts.success('Draft saved', `${updated.claimReference} was saved successfully.`);
    } catch {
      this.alerts.close();
      await this.alerts.error('Draft not saved', 'The report draft could not be saved.');
    }
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
      const optimized = await this.workflow.optimizeImage(file);
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
      if (this.offline.online()) {
        try {
          this.captureMessage.set('Reading tyre and vehicle details with AI…');
          const ai = await this.workflow.analyseImage(optimized.blob, file.name);
          this.applyOcrResult(ai, category);

          if (!Object.values(ai).some((value) => value.trim())) {
            this.captureMessage.set(
              'AI could not read any tyre or vehicle details from this image.',
            );
          }
        } catch (error) {
          const detail =
            error instanceof HttpErrorResponse
              ? (typeof error.error?.detail === 'string'
                  ? error.error.detail
                  : `AI request failed (HTTP ${error.status || 'network'}).`)
              : 'AI image analysis failed.';

          this.captureMessage.set(
            `AI could not populate the fields: ${detail}`,
          );
        }
      } else {
        this.captureMessage.set(
          'Photo captured offline. AI field extraction will be available when connected.',
        );
      }

      const current = {
        ...this.report(),
        ...this.form.getRawValue(),
        updatedAt: new Date().toISOString(),
      };
      this.report.set(current);
      await this.workflow.saveNow(current);
      const stored = await this.workflow.uploadImage(current.id, category, optimized.blob, file.name);
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
    if (!photo) return;
    if (!(await this.alerts.confirm(
      'Remove photo?',
      `${photo.label} will be removed from this technical report.`,
      'Remove photo',
      'warning',
      true,
    ))) return;
    try {
      if (photo.storageId) {
        await this.workflow.deleteImage(this.report().id, photo.storageId);
      } else {
        await this.workflow.removeQueuedImage(this.report().id, category);
      }
      this.report.update((r) => ({ ...r, photos: r.photos.filter((p) => p.category !== category) }));
      this.persist();
      await this.alerts.success('Photo removed', `${photo.label} was removed successfully.`);
    } catch {
      await this.alerts.error('Photo not removed', 'The photo could not be removed.');
    }
  }
  private applyOcrResult(ai: {
    brand: string;
    size: string;
    pattern: string;
    dot: string;
    serialNumber: string;
    vehicleMakeModel: string;
    rtd: string;
    comment: string;
  }, category: string): void {
    const patch: Record<string, string> = {};

    if (ai.brand && !this.form.controls.brand.value.trim()) patch['brand'] = ai.brand;
    if (ai.size && !this.form.controls.rimSize.value.trim()) patch['rimSize'] = ai.size;
    if (ai.pattern && !this.form.controls.pattern.value.trim()) patch['pattern'] = ai.pattern;
    if (ai.dot && !this.form.controls.dot.value.trim()) patch['dot'] = ai.dot;

    if (ai.serialNumber && !this.form.controls.serialNumber.value.trim()) {
      patch['serialNumber'] = ai.serialNumber;
    }

    if (ai.vehicleMakeModel && !this.form.controls.vehicleMakeModel.value.trim()) {
      patch['vehicleMakeModel'] = ai.vehicleMakeModel;
    }

    if (ai.rtd && !this.form.controls.remainingTreadDepth.value.trim()) {
      patch['remainingTreadDepth'] = ai.rtd;
    }

    if (ai.comment) {
      this.report.update((current) => ({
        ...current,
        photoComments: {
          ...(current.photoComments ?? {}),
          [category]: ai.comment,
        },
        photos: current.photos.map((photo) =>
          photo.category === category ? { ...photo, aiComment: ai.comment } : photo,
        ),
      }));
    }

    if (Object.keys(patch).length) {
      this.form.patchValue(patch);
    }

    if (Object.keys(patch).length || ai.comment) {
      this.captureMessage.set(
        'Photo saved. AI filled the fields it could read and added an image comment; please verify them.',
      );
    }
  }

  openTyrePositionModal(): void {
    const current = this.form.controls.tyrePosition.value;
    if (current.startsWith('Car - ')) this.tyreVehicleType.set('Car');
    else if (current.startsWith('Trailer - ')) this.tyreVehicleType.set('Trailer');
    else this.tyreVehicleType.set('Horse');
    this.tyrePositionModalOpen.set(true);
  }

  closeTyrePositionModal(): void {
    this.tyrePositionModalOpen.set(false);
  }

  selectTyreVehicleType(type: 'Car' | 'Horse' | 'Trailer'): void {
    this.tyreVehicleType.set(type);
  }

  selectTyrePosition(position: string): void {
    const value = `${this.tyreVehicleType()} - ${position}`;
    this.form.controls.tyrePosition.setValue(value);
    this.tyrePositionModalOpen.set(false);
    this.persist();
  }

  isTyrePosition(position: string): boolean {
    return this.form.controls.tyrePosition.value ===
      `${this.tyreVehicleType()} - ${position}`;
  }

  fieldError(field: string): string {
    const optionalFields = new Set([
      'returnedWithRim',
      'fittedLoose',
      'claimCode',
      'tyreMileage',
      'natureOfRepair',
      'goodsTransported',
      'vehicleMakeModel',
      'vehicleMileage',
    ]);
    if (optionalFields.has(field)) return '';

    const error = this.validationErrors()[field] ?? '';
    if (!error) return '';

    const control = this.form.get(field);
    if (!control) return error;

    return String(control.value ?? '').trim() ? '' : error;
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
  async sendReport(): Promise<'Queued' | DeliveryAttempt> {
    if (!(await this.validateStep(3)) || !this.hasSelectedRecipient()) {
      throw new Error('The report is not ready to send.');
    }

    const recipient = this.recipients().find(
      (item) => item.id === this.selectedRecipient(),
    );
    if (!recipient) throw new Error('The selected recipient is not available.');

    const current = {
      ...this.currentReport(),
      status: 'Submitted' as const,
    };
    this.report.set(current);
    await this.workflow.saveNow(current);

    if (!this.offline.online()) {
      await this.workflow.queueDelivery(
        current,
        recipient.id,
        recipient.email,
      );
      this.deliveryStatus.set('Queued');
      this.deliveryEmail.set(recipient.email);
      return 'Queued';
    }

    const result = await this.workflow.deliver(current, recipient.id);
    const updated = {
      ...this.report(),
      status: result.status === 'Sent'
        ? ('Email Sent' as const)
        : result.status === 'Failed'
          ? ('Email Failed' as const)
          : ('Submitted' as const),
    };
    this.report.set(updated);
    await this.workflow.saveNow(updated);
    this.deliveryStatus.set(result.status);
    this.deliveryEmail.set(result.recipient_email);
    return result;
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
      await this.workflow.saveNow(current);
      this.alerts.loading('Generating PDF…', 'Building the Royal Tyres technical report.');
      await this.workflow.downloadPdf(current);
      this.alerts.close();
      await this.alerts.success('PDF ready', `${current.claimReference} was generated successfully.`);
    } catch {
      this.alerts.close();
      this.captureMessage.set('PDF generation failed. Check the API connection and try again.');
      await this.alerts.error('PDF failed', 'The technical report PDF could not be generated.');
    } finally {
      this.pdfBusy.set(false);
    }
  }
  editReport(): void {
    this.previewMode.set(false);
    this.step.set(2);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  async sendFromPreview(): Promise<void> {
    const recipientId = this.selectedRecipient();
    if (!this.hasSelectedRecipient()) {
      await this.alerts.error(
        'Recipient required',
        'Select an email recipient before sending the report.',
      );
      return;
    }

    const recipient = this.recipients().find((item) => item.id === recipientId);
    const confirmed = await this.alerts.confirmReportSend(
      recipient?.email ?? 'Selected recipient',
      this.report().claimReference,
    );
    if (!confirmed) return;

    this.submitting.set(true);
    this.captureMessage.set('');
    this.alerts.sending();

    try {
      const result = await this.sendReport();
      this.alerts.close();

      if (result === 'Queued') {
        await this.alerts.success(
          'Report queued',
          `${this.report().claimReference} is saved on this device and will send automatically when the connection returns.`,
        );
        this.previewMode.set(false);
        this.successMode.set(true);
        window.scrollTo({ top: 0, behavior: 'smooth' });
        return;
      }

      if (result.status === 'Sent') {
        await this.alerts.success(
          'Report accepted',
          `${this.report().claimReference} was accepted by the mail server for ${this.deliveryEmail() || recipient?.email || 'the selected recipient'}.`,
        );
        this.previewMode.set(false);
        this.successMode.set(true);
        window.scrollTo({ top: 0, behavior: 'smooth' });
        return;
      }

      if (result.status === 'Failed') {
        await this.alerts.error(
          'Email delivery failed',
          result.error_message ||
            'The recipient could not receive the email. The failed delivery was saved in Delivery Centre for reporting and retry.',
        );
        this.captureMessage.set(
          'Email delivery failed. The failure is available in Delivery Centre.',
        );
        return;
      }

      await this.alerts.warning(
        'Email not delivered yet',
        result.error_message
          ? `The delivery could not complete and will be retried automatically. ${result.error_message}`
          : 'The delivery could not complete and will be retried automatically. You can track it in Delivery Centre.',
      );
      this.captureMessage.set(
        'Email is waiting for retry. Track the delivery in Delivery Centre.',
      );
    } catch {
      this.alerts.close();
      await this.alerts.error(
        'Report not sent',
        'The report could not be delivered. Check the email configuration or Delivery Centre for the error.',
      );
      this.captureMessage.set(
        'The report could not be sent. Check the API connection and try again.',
      );
    } finally {
      this.submitting.set(false);
    }
  }
  async startAnotherReport(): Promise<void> {
    if (!(await this.alerts.confirm(
      'Start another report?',
      'A new blank technical report will be opened.',
      'Start new report',
    ))) return;
    void this.router.navigate(['/reports/new']).then(() => window.location.reload());
  }
  private async loadCustomerSuggestions(term: string): Promise<void> {
    this.customerLookupBusy.set(true);
    try {
      const customers = await this.workflow.customerSuggestions(term);
      if (this.form.controls.customerName.value.trim() !== term) return;

      this.customerMatches.set(customers.slice(0, 20));
      this.customerDropdownOpen.set(true);
    } catch {
      this.customerMatches.set([]);
      // Customer entry remains free text when lookup is unavailable.
    } finally {
      this.customerLookupBusy.set(false);
    }
  }

  private async loadDeliveryData(): Promise<void> {
    try {
      const current = this.currentReport();
      const recipients = await this.workflow.recipients(current);
      this.recipients.set(recipients);

      // Recipient selection must always be an explicit user choice.
      // Clear stale selections when branch/category changes or no longer matches.
      if (!recipients.some((recipient) => recipient.id === this.selectedRecipient())) {
        this.selectedRecipient.set('');
      }
    } catch {
      this.recipients.set([]);
      this.captureMessage.set('Delivery contacts are temporarily unavailable.');
    }
  }
  private async loadReferenceData(): Promise<void> {
    try {
      const data = await this.workflow.referenceData();
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
  private clearResolvedValidationErrors(): void {
    const current = this.form.getRawValue();
    const errors = { ...this.validationErrors() };

    const textFields = [
      'salesperson',
      'customerName',
      'branch',
      'brand',
      'rimSize',
      'pattern',
      'dot',
      'serialNumber',
      'remainingTreadDepth',
      'inspectedPressure',
      'inspectedLocation',
      'fittedLoose',
      'claimCode',
      'tyreMileage',
      'natureOfRepair',
      'goodsTransported',
      'vehicleMakeModel',
      'vehicleMileage',
      'tyrePosition',
    ] as const;

    for (const field of textFields) {
      if (String(current[field] ?? '').trim()) {
        delete errors[field];
      }
    }

    if (current.returnedWithRim !== null) {
      delete errors['returnedWithRim'];
    }

    this.validationErrors.set(errors);

    if (!Object.keys(errors).length && this.captureMessage() === 'Correct the highlighted fields before continuing.') {
      this.captureMessage.set('');
    }
  }

  private async validateStep(step: number): Promise<boolean> {
    this.persist();
    try {
      const result = await this.workflow.validate(this.currentReport(), step);
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
    if (!id) return this.workflow.createReport();
    return this.workflow.getLocalReport(id) ?? { ...this.workflow.createReport(), id };
  }
  private async loadServerReport(): Promise<void> {
    try {
      const loaded = await this.workflow.loadReport(this.report().id);
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
      this.workflow.save(updated);
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
