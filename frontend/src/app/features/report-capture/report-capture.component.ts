import { Component, computed, effect, inject, OnDestroy, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { debounceTime, Subject, takeUntil } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { ReportStore } from '../../core/data/report.store';
import { PHOTO_CATEGORIES, ReportPhoto, TechnicalReport } from '../../shared/models/report.models';
@Component({
  selector: 'app-report-capture',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <section class="capture-page">
      <header class="capture-header">
        <a routerLink="/reports" class="back">←</a>
        <div>
          <p>{{ report().claimReference }}</p>
          <h1>Technical report</h1>
        </div>
        <div class="save-state">
          <span [class.saved]="saved()">{{ saved() ? '✓ Saved' : 'Saving…' }}</span
          ><button class="button secondary" type="button" (click)="saveDraft()">Save draft</button>
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
              <div class="photo-grid">
                @for (item of photoCategories; track item.key) {
                  <article class="photo-slot" [class.complete]="photoFor(item.key)">
                    @if (photoFor(item.key); as photo) {
                      <img [src]="photo.previewUrl" [alt]="item.label" />
                      <div class="photo-overlay">
                        <button type="button" (click)="removePhoto(item.key)">Remove</button>
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
                    </div>
                    <label class="capture-button"
                      ><input
                        type="file"
                        accept="image/*"
                        capture="environment"
                        (change)="capture($event, item.key)"
                      />{{ photoFor(item.key) ? 'Replace' : 'Capture photo' }}</label
                    >
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
              <div class="next-phase">
                <span>PDF & email delivery</span>
                <p>
                  This report is ready for Phase 3 PDF generation once all required information and
                  photographs are complete.
                </p>
              </div>
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
            <a class="button primary" routerLink="/reports">Finish review</a>
          }
        </footer>
      </form>
    </section>
  `,
  styleUrl: './report-capture.component.scss',
})
export class ReportCaptureComponent implements OnDestroy {
  private readonly fb = inject(FormBuilder);
  private readonly route = inject(ActivatedRoute);
  private readonly store = inject(ReportStore);
  private readonly auth = inject(AuthService);
  private readonly destroy$ = new Subject<void>();
  readonly step = signal(0);
  readonly saved = signal(true);
  readonly stepLabels = ['Claim', 'Tyre', 'Photos', 'Review'];
  readonly photoCategories = PHOTO_CATEGORIES;
  readonly requiredCount = PHOTO_CATEGORIES.filter((p) => p.required).length;
  readonly report = signal<TechnicalReport>(this.loadReport());
  readonly form = this.fb.nonNullable.group({
    internalExternal: [this.report().internalExternal],
    branch: [this.report().branch],
    salesperson: [this.report().salesperson],
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
  constructor() {
    if (!this.form.controls.salesperson.value)
      this.form.controls.salesperson.setValue(this.auth.user()?.full_name ?? '');
    this.form.valueChanges
      .pipe(debounceTime(650), takeUntil(this.destroy$))
      .subscribe(() => this.persist());
    effect(() => {
      this.report().photos;
    });
    this.persist();
  }
  ngOnDestroy(): void {
    this.persist();
    this.destroy$.next();
    this.destroy$.complete();
  }
  goTo(value: number): void {
    this.step.set(value);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  next(): void {
    if (this.step() < 3) this.goTo(this.step() + 1);
  }
  previous(): void {
    if (this.step() > 0) this.goTo(this.step() - 1);
  }
  saveDraft(): void {
    this.persist();
  }
  photoFor(category: string): ReportPhoto | undefined {
    return this.report().photos.find((p) => p.category === category);
  }
  capture(event: Event, category: string): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const photo: ReportPhoto = {
        category,
        name: file.name,
        previewUrl: String(reader.result),
        capturedAt: new Date().toISOString(),
      };
      this.report.update((r) => ({
        ...r,
        photos: [...r.photos.filter((p) => p.category !== category), photo],
      }));
      this.persist();
    };
    reader.readAsDataURL(file);
    input.value = '';
  }
  removePhoto(category: string): void {
    this.report.update((r) => ({ ...r, photos: r.photos.filter((p) => p.category !== category) }));
    this.persist();
  }
  private loadReport(): TechnicalReport {
    const id = this.route.snapshot.paramMap.get('id');
    return (id && this.store.get(id)) || this.store.create();
  }
  private persist(): void {
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
}
