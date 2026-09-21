import { computed, Injectable, signal } from '@angular/core';
import { TechnicalReport } from '../../shared/models/report.models';
const REPORTS_KEY = 'royal-tyres.reports';
@Injectable({ providedIn: 'root' })
export class ReportStore {
  private readonly state = signal<TechnicalReport[]>(this.load());
  readonly reports = this.state.asReadonly();
  readonly drafts = computed(() => this.state().filter((report) => report.status === 'Draft'));
  get(id: string): TechnicalReport | undefined {
    return this.state().find((report) => report.id === id);
  }
  save(report: TechnicalReport): void {
    const reports = this.state();
    const updated = reports.some((item) => item.id === report.id)
      ? reports.map((item) => (item.id === report.id ? report : item))
      : [report, ...reports];
    this.state.set(updated);
    localStorage.setItem(REPORTS_KEY, JSON.stringify(updated));
  }
  create(): TechnicalReport {
    const now = new Date().toISOString();
    return {
      id: crypto.randomUUID(),
      claimReference: `TR-${new Date().getFullYear()}-${String(this.state().length + 1).padStart(4, '0')}`,
      createdAt: now,
      updatedAt: now,
      status: 'Draft',
      branch: 'Phoenix',
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
  private load(): TechnicalReport[] {
    try {
      return JSON.parse(localStorage.getItem(REPORTS_KEY) ?? '[]') as TechnicalReport[];
    } catch {
      return [];
    }
  }
}
