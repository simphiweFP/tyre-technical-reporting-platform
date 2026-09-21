import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { ReportStore } from '../../core/data/report.store';
@Component({
  selector: 'app-report-list',
  imports: [DatePipe, FormsModule, RouterLink],
  template: `
    <section class="page">
      <header class="page-header">
        <div>
          <p class="eyebrow">Technical reports</p>
          <h1>Report history</h1>
          <p>Find drafts and completed tyre inspections.</p>
        </div>
        @if (canCapture()) {
          <a routerLink="/reports/new" class="button primary">＋ New report</a>
        }
      </header>
      <div class="toolbar card">
        <label class="search"
          ><span>⌕</span
          ><input
            [(ngModel)]="query"
            placeholder="Search claim, customer, invoice or serial number"
            aria-label="Search reports" /></label
        ><select [(ngModel)]="status" aria-label="Filter by status">
          <option value="">All statuses</option>
          <option>Draft</option>
          <option>Ready to Submit</option>
          <option>Submitted</option>
          <option>Email Sent</option>
          <option>Email Failed</option>
        </select>
      </div>
      <div class="table-card card">
        @if (filtered().length) {
          <div class="table-header">
            <span>Report</span><span>Customer</span><span>Tyre</span><span>Updated</span
            ><span>Status</span><span></span>
          </div>
          @for (report of filtered(); track report.id) {
            <a class="table-row" [routerLink]="['/reports', report.id, 'edit']"
              ><div>
                <strong>{{ report.claimReference }}</strong
                ><small>{{ report.branch }}</small>
              </div>
              <div>
                <strong>{{ report.customerName || 'Not captured' }}</strong
                ><small>{{ report.customerInvoiceNumber || 'No invoice' }}</small>
              </div>
              <div>
                <strong>{{ report.brand || 'Pending' }}</strong
                ><small>{{ report.serialNumber || 'No serial number' }}</small>
              </div>
              <time
                >{{ report.updatedAt | date: 'd MMM y'
                }}<small>{{ report.updatedAt | date: 'HH:mm' }}</small></time
              ><span class="status" [class]="statusClass(report.status)">{{ report.status }}</span
              ><b>›</b></a
            >
          }
        } @else {
          <div class="empty-state">
            <span>⌕</span>
            <h2>No matching reports</h2>
            <p>Try another search or start a new technical report.</p>
          </div>
        }
      </div>
    </section>
  `,
  styleUrl: './report-list.component.scss',
})
export class ReportListComponent {
  readonly store = inject(ReportStore);
  readonly auth = inject(AuthService);
  readonly query = signal('');
  readonly status = signal('');
  readonly canCapture = computed(() => this.auth.hasRole('administrator', 'report_capturer'));
  readonly filtered = computed(() => {
    const query = this.query().trim().toLowerCase();
    return this.store
      .reports()
      .filter(
        (r) =>
          (!this.status() || r.status === this.status()) &&
          (!query ||
            [
              r.claimReference,
              r.customerName,
              r.customerInvoiceNumber,
              r.serialNumber,
              r.brand,
              r.branch,
            ].some((v) => v.toLowerCase().includes(query))),
      );
  });
  statusClass(value: string): string {
    return value.toLowerCase().replaceAll(' ', '-');
  }
}
