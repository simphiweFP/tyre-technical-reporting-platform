import { DatePipe } from '@angular/common';
import { Component, computed, effect, inject, OnDestroy, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { debounceTime, Subject, takeUntil } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { ReportStore } from '../../core/data/report.store';
import { ReportDeliveryService } from '../../core/delivery/report-delivery.service';
import { ReportIntelligenceService } from '../../core/media/report-intelligence.service';
import {
  DeliveryAttempt,
  PHOTO_CATEGORIES,
  ReportPhoto,
  ReportRecipient,
  TechnicalReport,
} from '../../shared/models/report.models';
@Component({
  selector: 'app-report-capture',
  imports: [ReactiveFormsModule, RouterLink, DatePipe],
  templateUrl: './report-capture.component.html',
  /* Legacy inline markup retained temporarily for migration history.
    <section class="capture-page">
      <header class="capture-header">
        <a routerLink="/reports" class="back">←</a>
        <div>
          <p>{{ report().claimReference }}</p>
          <h1>Technical report</h1>
        </div>
        <div class="save-state">
          <span [class.saved]="saved()">{{
            store.saveError() ? 'Not saved' : saved() ? '✓ Saved' : 'Saving…'
          }}</span>
          @if (!readonlyView()) {
            <button class="button secondary" type="button" (click)="saveDraft()">Save draft</button>
          }
        </div>
      </header>
      <div class="step-bar">
        @for (label of stepLabels; track label; let index = $index) {
          <button
            [class.active]="step() === index"
            [class.done]="step() > index"
            (click)="goTo(index)"
          >
            <span>{{ step() > index ? '✓' : index + 1 }}</span
            >{{ label }}
          </button>
        }
        <div class="progress"><i [style.width.%]="progress()"></i></div>
      </div>
      <form [formGroup]="form" (ngSubmit)="next()">
        <div class="capture-layout">
          <main class="form-card card">
            @if (captureMessage() && step() !== 2) {
              <div class="validation-callout" role="status">{{ captureMessage() }}</div>
            }
            @if (step() === 0) {
              <div class="section-title">
                <span>01</span>
                <div>
                  <h2>Claim information</h2>
                  <p>Start with the customer and inspection context.</p>
                </div>
              </div>
              <div class="form-grid">
                <div class="field">
                  <label>Internal or external</label
                  ><select formControlName="internalExternal">
                    <option>Internal</option>
                    <option>External</option>
                  </select>
                </div>
                <div class="field">
                  <label>Branch</label
                  ><select formControlName="branch">
                    <option>Phoenix</option>
                    <option>Durban</option>
                    <option>Johannesburg</option>
                  </select>
                </div>
                <div class="field">
                  <label>Salesperson / technician</label
                  ><input formControlName="salesperson" placeholder="Select or enter name" />
                </div>
                <div class="field">
                  <label>Customer name *</label
                  ><input formControlName="customerName" placeholder="Search or enter customer" />
                </div>
                <div class="field">
                  <label>Customer invoice number *</label
                  ><input formControlName="customerInvoiceNumber" placeholder="e.g. INV-10482" />
                </div>
                <div class="field">
                  <label>Claim category</label
                  ><select formControlName="category">
                    <option value="">Select category</option>
                    <option>Manufacturing</option>
                    <option>Road hazard</option>
                    <option>Service related</option>
                    <option>Other</option>
                  </select>
                </div>
                <div class="field">
                  <label>Inspected location</label
                  ><input
                    formControlName="inspectedLocation"
                    placeholder="Branch or customer site"
                  />
                </div>
                <div class="field">
                  <label>Fitted or loose</label
                  ><select formControlName="fittedLoose">
                    <option value="">Select option</option>
                    <option>Fitted</option>
                    <option>Loose</option>
                  </select>
                </div>
              </div>
            }
            @if (step() === 1) {
              <div class="section-title">
                <span>02</span>
                <div>
                  <h2>Tyre and vehicle</h2>
                  <p>Capture the markings and inspection measurements.</p>
                </div>
              </div>
              @if (suggestions().length) {
                <section class="suggestion-panel" aria-live="polite">
                  <div>
                    <span>OCR-assisted suggestions</span>
                    <p>Review each value before applying it. Nothing is filled automatically.</p>
                  </div>
                  @for (suggestion of suggestions(); track suggestion.field) {
                    <article>
                      <div>
                        <small>{{ fieldLabel(suggestion.field) }}</small>
                        <strong>{{ suggestion.value }}</strong>
                        <em>{{ confidence(suggestion.confidence) }} confidence</em>
                      </div>
                      @if (suggestion.field !== 'tyreSize') {
                        <button type="button" (click)="acceptSuggestion(suggestion)">
                          Use value
                        </button>
                      }
                    </article>
                  }
                </section>
              }
              <div class="form-grid">
                <div class="field">
                  <label>Brand *</label
                  ><input formControlName="brand" placeholder="e.g. Bridgestone" />
                </div>
                <div class="field">
                  <label>Rim size</label><input formControlName="rimSize" placeholder="e.g. R16" />
                </div>
                <div class="field">
                  <label>Pattern</label
                  ><input formControlName="pattern" placeholder="Tyre pattern" />
                </div>
                <div class="field">
                  <label>DOT *</label><input formControlName="dot" placeholder="DOT marking" />
                </div>
                <div class="field">
                  <label>Serial number *</label
                  ><input formControlName="serialNumber" placeholder="Full serial number" />
                </div>
                <div class="field">
                  <label>Claim code / description</label
                  ><input formControlName="claimCode" placeholder="Claim code" />
                </div>
                <div class="field">
                  <label>Remaining tread depth (mm)</label
                  ><input formControlName="remainingTreadDepth" inputmode="decimal" />
                </div>
                <div class="field">
                  <label>Inspected pressure</label
                  ><input formControlName="inspectedPressure" inputmode="decimal" />
                </div>
                <div class="field">
                  <label>Tyre mileage</label
                  ><input formControlName="tyreMileage" inputmode="numeric" />
                </div>
                <div class="field">
                  <label>Tyre position</label
                  ><select formControlName="tyrePosition">
                    <option value="">Select position</option>
                    <option>Front left</option>
                    <option>Front right</option>
                    <option>Rear left</option>
                    <option>Rear right</option>
                    <option>Spare</option>
                  </select>
                </div>
                <div class="field">
                  <label>Nature of repair</label><input formControlName="natureOfRepair" />
                </div>
                <div class="field">
                  <label>Vehicle make / model</label><input formControlName="vehicleMakeModel" />
                </div>
                <div class="field">
                  <label>Vehicle mileage</label
                  ><input formControlName="vehicleMileage" inputmode="numeric" />
                </div>
                <div class="field">
                  <label>Goods transported</label><input formControlName="goodsTransported" />
                </div>
                <div class="field full">
                  <label>Other relevant information</label
                  ><textarea
                    formControlName="notes"
                    placeholder="Add relevant inspection context"
                  ></textarea>
                </div>
              </div>
            }
            @if (step() === 2) {
              <div class="section-title">
                <span>03</span>
                <div>
                  <h2>Guided photographs</h2>
                  <p>{{ photoCount() }} of {{ requiredCount }} required photographs captured.</p>
                </div>
              </div>
              @if (captureMessage()) {
                <div class="validation-callout" role="status">{{ captureMessage() }}</div>
              }
              <div class="photo-grid">
                @for (item of photoCategories; track item.key) {
                  <article class="photo-slot" [class.complete]="photoFor(item.key)">
                    @if (photoFor(item.key); as photo) {
                      <img [src]="photo.previewUrl" [alt]="item.label" />
                      <div class="photo-overlay">
                        @if (!readonlyView()) {
                          <button type="button" (click)="removePhoto(item.key)">Remove</button>
                        }
                      </div>
                    } @else {
                      <div class="camera-icon">▣<b>＋</b></div>
                    }
                    <div class="photo-copy">
                      <strong
                        >{{ item.label }}
                        @if (item.required) {
                          <em>*</em>
                        }</strong
                      ><small>{{ item.hint }}</small>
                      @if (analysingCategory() === item.key) {
                        <small class="analysing">Reading tyre markings…</small>
                      }
                    </div>
                    @if (!readonlyView()) {
                      <label class="capture-button"
                        ><input
                          type="file"
                          accept="image/*"
                          capture="environment"
                          (change)="capture($event, item.key)"
                        />{{ photoFor(item.key) ? 'Replace' : 'Capture photo' }}</label
                      >
                    }
                  </article>
                }
              </div>
            }
            @if (step() === 3) {
              <div class="section-title">
                <span>04</span>
                <div>
                  <h2>Review report</h2>
                  <p>Confirm the information before PDF generation and email delivery.</p>
                </div>
              </div>
              <div class="review-grid">
                <section>
                  <h3>Claim</h3>
                  <dl>
                    <div>
                      <dt>Reference</dt>
                      <dd>{{ report().claimReference }}</dd>
                    </div>
                    <div>
                      <dt>Customer</dt>
                      <dd>{{ form.value.customerName || 'Not captured' }}</dd>
                    </div>
                    <div>
                      <dt>Invoice</dt>
                      <dd>{{ form.value.customerInvoiceNumber || 'Not captured' }}</dd>
                    </div>
                    <div>
                      <dt>Branch</dt>
                      <dd>{{ form.value.branch }}</dd>
                    </div>
                  </dl>
                  <button type="button" (click)="goTo(0)">Edit claim details</button>
                </section>
                <section>
                  <h3>Tyre</h3>
                  <dl>
                    <div>
                      <dt>Brand / size</dt>
                      <dd>{{ form.value.brand || 'Pending' }} {{ form.value.rimSize }}</dd>
                    </div>
                    <div>
                      <dt>DOT</dt>
                      <dd>{{ form.value.dot || 'Not captured' }}</dd>
                    </div>
                    <div>
                      <dt>Serial number</dt>
                      <dd>{{ form.value.serialNumber || 'Not captured' }}</dd>
                    </div>
                    <div>
                      <dt>Vehicle</dt>
                      <dd>{{ form.value.vehicleMakeModel || 'Not captured' }}</dd>
                    </div>
                  </dl>
                  <button type="button" (click)="goTo(1)">Edit tyre details</button>
                </section>
                <section class="photo-summary">
                  <h3>Photographs</h3>
                  <strong>{{ photoCount() }} / {{ requiredCount }}</strong>
                  <p>required images captured</p>
                  <button type="button" (click)="goTo(2)">Review photographs</button>
                </section>
              </div>
              @if (duplicateWarning()) {
                <div class="validation-callout">{{ duplicateWarning() }}</div>
              }
              <div class="next-phase ready">
                <span>Royal Tyres PDF</span>
                <p>Generate a branded, email-ready PDF containing the report and photographs.</p>
                <button
                  class="button primary"
                  type="button"
                  [disabled]="pdfBusy()"
                  (click)="downloadPdf()"
                >
                  {{ pdfBusy() ? 'Generating…' : 'Download PDF' }}
                </button>
              </div>
              <section class="delivery-panel">
                <div>
                  <span>Third-party delivery</span>
                  <p>Send the PDF to an approved recipient. No approval step is required.</p>
                </div>
                <select [value]="selectedRecipient()" (change)="selectRecipient($event)">
                  <option value="">Select a recipient</option>
                  @for (recipient of recipients(); track recipient.id) {
                    <option [value]="recipient.id">
                      {{ recipient.company }} · {{ recipient.email }}
                    </option>
                  }
                </select>
                <button
                  class="button primary"
                  type="button"
                  [disabled]="deliveryBusy() || !selectedRecipient()"
                  (click)="sendReport()"
                >
                  {{ deliveryBusy() ? 'Sending…' : 'Email PDF' }}
                </button>
              </section>
              @if (deliveryMessage()) {
                <div class="validation-callout" role="status">{{ deliveryMessage() }}</div>
              }
              @if (deliveryHistory().length) {
                <section class="delivery-history">
                  <h3>Delivery history</h3>
                  @for (item of deliveryHistory(); track item.id) {
                    <article>
                      <div>
                        <strong>{{ item.recipient_email }}</strong>
                        <small>{{ item.last_attempt_at | date: 'medium' }}</small>
                      </div>
                      <span [class.failed]="item.status === 'Failed'">
                        {{ item.status }} · attempt {{ item.attempt_count }}
                      </span>
                      @if (item.status === 'Failed') {
                        <button type="button" (click)="retryDelivery(item.id)">Retry</button>
                      }
                    </article>
                  }
                </section>
              }
            }
          </main>
          <aside class="context-card card">
            <p class="eyebrow">Report progress</p>
            <h3>{{ report().claimReference }}</h3>
            <ul>
              <li [class.complete]="claimComplete()">
                <span>{{ claimComplete() ? '✓' : '1' }}</span
                >Claim details
              </li>
              <li [class.complete]="tyreComplete()">
                <span>{{ tyreComplete() ? '✓' : '2' }}</span
                >Tyre details
              </li>
              <li [class.complete]="photosComplete()">
                <span>{{ photosComplete() ? '✓' : '3' }}</span
                >Photographs
              </li>
            </ul>
            <div class="auto-save">
              <span>☁</span>
              <div>
                <strong>Automatic drafts</strong
                ><small>Your changes are saved on this device as you work.</small>
              </div>
            </div>
          </aside>
        </div>
        <footer class="capture-footer">
          <button type="button" class="button ghost" [disabled]="step() === 0" (click)="previous()">
            ← Previous</button
          ><span>Step {{ step() + 1 }} of 4</span>
          @if (step() < 3) {
            <button class="button primary" type="submit">Continue →</button>
          } @else {
            <a class="button secondary" routerLink="/reports">Finish review</a>
          }
        </footer>
      </form>
    </section>
  */
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
  private readonly destroy$ = new Subject<void>();
  readonly step = signal(0);
  readonly saved = signal(true);
  readonly captureMessage = signal('');
  readonly pdfBusy = signal(false);
  readonly readonlyView = computed(() => this.auth.hasRole('viewer'));
  readonly deliveryBusy = signal(false);
  readonly deliveryMessage = signal('');
  readonly recipients = signal<ReportRecipient[]>([]);
  readonly selectedRecipient = signal('');
  readonly deliveryHistory = signal<DeliveryAttempt[]>([]);
  readonly previewMode = signal(false);
  readonly savedMode = signal(false);
  readonly confirmed = signal(false);
  readonly photoValidationShown = signal(false);
  readonly stepLabels = ['Report details', 'Take photos', 'Tyre & vehicle', 'Review'];
  readonly photoCategories = PHOTO_CATEGORIES;
  readonly requiredCount = PHOTO_CATEGORIES.filter((p) => p.required).length;
  readonly report = signal<TechnicalReport>(this.loadReport());
  readonly form = this.fb.nonNullable.group({
    internalExternal: [this.report().internalExternal],
    branch: [this.report().branch],
    salesperson: [this.report().salesperson, Validators.required],
    customerName: [this.report().customerName, Validators.required],
    customerInvoiceNumber: [this.report().customerInvoiceNumber, Validators.required],
    category: [this.report().category],
    inspectedLocation: [this.report().inspectedLocation],
    returnedWithRim: [this.report().returnedWithRim],
    fittedLoose: [this.report().fittedLoose],
    brand: [this.report().brand, Validators.required],
    rimSize: [this.report().rimSize],
    pattern: [this.report().pattern],
    dot: [this.report().dot, Validators.required],
    serialNumber: [this.report().serialNumber, Validators.required],
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
  readonly progress = computed(() => (this.step() / 3) * 100);
  readonly photoCount = computed(
    () =>
      this.report().photos.filter(
        (photo) => PHOTO_CATEGORIES.find((p) => p.key === photo.category)?.required,
      ).length,
  );
  readonly claimComplete = computed(
    () =>
      !!this.form.controls.customerName.value && !!this.form.controls.customerInvoiceNumber.value,
  );
  readonly tyreComplete = computed(
    () =>
      !!this.form.controls.brand.value &&
      !!this.form.controls.dot.value &&
      !!this.form.controls.serialNumber.value,
  );
  readonly photosComplete = computed(() => this.photoCount() === this.requiredCount);
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
    if (!this.form.controls.salesperson.value)
      this.form.controls.salesperson.setValue(this.auth.user()?.full_name ?? '');
    this.form.valueChanges
      .pipe(debounceTime(650), takeUntil(this.destroy$))
      .subscribe(() => this.persist());
    effect(() => {
      this.report().photos;
    });
    effect(() => {
      this.saved.set(!this.store.saving() && !this.store.saveError());
    });
    void this.loadDeliveryData();
    if (this.route.snapshot.paramMap.get('id')) void this.loadServerReport();
    else this.persist();
  }
  ngOnDestroy(): void {
    if (!this.readonlyView()) this.persist();
    this.destroy$.next();
    this.destroy$.complete();
  }
  goTo(value: number): void {
    if (value > this.step()) {
      if (value > this.step() + 1 || !this.validateStep(this.step())) return;
      if (value === 3 && !this.readyForReview()) return;
    }
    this.step.set(value);
    if (value === 3) void this.loadDeliveryData();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  async next(): Promise<void> {
    if (this.step() < 3) {
      this.goTo(this.step() + 1);
      return;
    }
    if (!this.confirmed() || !this.readyForReview()) return;
    this.captureMessage.set('');
    try {
      const submitted = { ...this.currentReport(), status: 'Submitted' as const };
      this.report.set(submitted);
      await this.store.saveNow(submitted);
      if (this.selectedRecipient()) await this.sendReport();
      await this.router.navigate(['/dashboard']);
    } catch {
      this.captureMessage.set(
        'The report could not be submitted. Check the API connection and try again.',
      );
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
      this.report.update((r) => ({
        ...r,
        photos: r.photos.map((item) =>
          item.category === category ? { ...item, storageId: stored.id } : item,
        ),
      }));
      this.persist();
    } catch {
      this.captureMessage.set('The image could not be processed. Try another photo.');
    }
  }
  async removePhoto(category: string): Promise<void> {
    const photo = this.photoFor(category);
    if (photo?.storageId) await this.store.deleteImage(this.report().id, photo.storageId);
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
  async downloadPdf(): Promise<void> {
    if (!this.readyForReview()) return;
    const current = this.currentReport();
    this.report.set(current);
    await this.store.saveNow(current);
    this.pdfBusy.set(true);
    try {
      await this.intelligence.downloadPdf(this.report());
      const updated = { ...this.report(), status: 'Ready to Submit' as const };
      this.report.set(updated);
      await this.store.saveNow(updated);
    } catch {
      this.captureMessage.set('PDF generation failed. Check the API connection and try again.');
    } finally {
      this.pdfBusy.set(false);
    }
  }
  selectRecipient(event: Event): void {
    this.selectedRecipient.set((event.target as HTMLSelectElement).value);
  }
  async sendReport(): Promise<void> {
    if (!this.readyForReview() || !this.selectedRecipient()) return;
    this.deliveryBusy.set(true);
    this.deliveryMessage.set('');
    try {
      const current = this.currentReport();
      this.report.set(current);
      await this.store.saveNow(current);
      const result = await this.delivery.deliver(this.report(), this.selectedRecipient());
      this.deliveryMessage.set(
        result.status === 'Pending' || result.status === 'Retrying'
          ? `PDF queued for delivery to ${result.recipient_email}.`
          : result.status === 'Sent'
            ? `PDF emailed to ${result.recipient_email}.`
            : `Delivery failed: ${result.error_message || 'SMTP service unavailable'}`,
      );
      const updated = {
        ...this.report(),
        status:
          result.status === 'Sent'
            ? ('Email Sent' as const)
            : result.status === 'Failed'
              ? ('Email Failed' as const)
              : ('Submitted' as const),
      };
      this.report.set(updated);
      await this.store.saveNow(updated);
      await this.loadHistory();
    } catch {
      this.deliveryMessage.set('The delivery request could not be completed. Try again.');
    } finally {
      this.deliveryBusy.set(false);
    }
  }
  async sendFromPreview(): Promise<void> {
    if (this.selectedRecipient()) await this.sendReport();
    else await this.downloadPdf();
    this.previewMode.set(false);
    this.savedMode.set(true);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  startAnotherReport(): void {
    window.location.assign('/reports/new');
  }
  async retryDelivery(deliveryId: string): Promise<void> {
    this.deliveryBusy.set(true);
    try {
      const result = await this.delivery.retry(deliveryId);
      this.deliveryMessage.set(
        result.status === 'Sent'
          ? `Retry succeeded for ${result.recipient_email}.`
          : `Retry failed: ${result.error_message || 'SMTP service unavailable'}`,
      );
      await this.loadHistory();
    } catch {
      this.deliveryMessage.set('The retry request could not be completed. Try again.');
    } finally {
      this.deliveryBusy.set(false);
    }
  }
  private async loadDeliveryData(): Promise<void> {
    try {
      const current = this.currentReport();
      const [recipients] = await Promise.all([
        this.delivery.recipients(true, current.branch, current.category),
        this.loadHistory(),
      ]);
      this.recipients.set(recipients);
      if (!this.selectedRecipient() && recipients.length) {
        this.selectedRecipient.set(recipients[0].id);
      }
    } catch {
      this.deliveryMessage.set('Delivery contacts are temporarily unavailable.');
    }
  }
  private async loadHistory(): Promise<void> {
    this.deliveryHistory.set(await this.delivery.history(this.report().claimReference));
  }
  private readyForReview(): boolean {
    this.persist();
    if (!this.claimComplete()) {
      this.step.set(0);
      this.captureMessage.set('Complete the required customer and invoice fields.');
      return false;
    }
    if (!this.photosComplete()) {
      this.step.set(1);
      const remaining = this.requiredCount - this.photoCount();
      this.captureMessage.set(
        `Capture ${remaining} remaining required photograph${remaining === 1 ? '' : 's'}.`,
      );
      return false;
    }
    if (!this.tyreComplete()) {
      this.step.set(2);
      this.captureMessage.set('Complete the required brand, DOT and serial number fields.');
      return false;
    }
    return true;
  }
  private validateStep(step: number): boolean {
    if (step === 0) {
      const controls = [
        this.form.controls.salesperson,
        this.form.controls.customerName,
        this.form.controls.customerInvoiceNumber,
      ];
      controls.forEach((control) => control.markAsTouched());
      if (controls.some((control) => control.invalid)) {
        this.captureMessage.set('Complete the highlighted required fields before continuing.');
        return false;
      }
    }
    if (step === 1 && !this.photosComplete()) {
      this.photoValidationShown.set(true);
      const remaining = this.requiredCount - this.photoCount();
      this.captureMessage.set(
        `Capture ${remaining} remaining required photograph${remaining === 1 ? '' : 's'} before continuing.`,
      );
      return false;
    }
    if (step === 2) {
      const controls = [
        this.form.controls.brand,
        this.form.controls.dot,
        this.form.controls.serialNumber,
      ];
      controls.forEach((control) => control.markAsTouched());
      if (controls.some((control) => control.invalid)) {
        this.captureMessage.set('Complete the highlighted tyre fields before continuing.');
        return false;
      }
    }
    this.captureMessage.set('');
    return true;
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
      await this.loadHistory();
    } catch {
      this.captureMessage.set('This report could not be loaded from the server.');
    }
  }
  private persist(): void {
    if (this.readonlyView()) return;
    this.saved.set(false);
    const value = this.form.getRawValue();
    const updated = { ...this.report(), ...value, updatedAt: new Date().toISOString() };
    this.report.set(updated);
    try {
      this.store.save(updated);
      this.saved.set(true);
    } catch {
      this.saved.set(false);
    }
  }
  private currentReport(): TechnicalReport {
    return {
      ...this.report(),
      ...this.form.getRawValue(),
      updatedAt: new Date().toISOString(),
    };
  }
}
