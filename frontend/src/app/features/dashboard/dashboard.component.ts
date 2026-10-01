import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { ReportAnalytics, ReportStore } from '../../core/data/report.store';
import { TechnicalReport } from '../../shared/models/report.models';

@Component({
  selector: 'app-dashboard',
  imports: [DatePipe, RouterLink],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent {
  readonly auth = inject(AuthService);
  readonly store = inject(ReportStore);
  readonly firstName = computed(() => this.auth.user()?.full_name.split(' ')[0] ?? 'there');
  readonly isAdmin = computed(() => this.auth.hasRole('administrator'));
  readonly isCapturer = computed(() => this.auth.hasRole('report_capturer'));
  readonly isViewer = computed(() => this.auth.hasRole('viewer'));
  readonly canCapture = computed(() => this.isAdmin() || this.isCapturer());
  readonly recent = computed(() => this.store.reports().slice(0, 6));
  readonly latestDraft = computed(() => this.store.reports().find((report) => report.status === 'Draft') ?? null);
  readonly analytics = signal<ReportAnalytics | null>(null);
  readonly workflowStatuses = ['Draft', 'Ready to Submit', 'Submitted', 'Email Sent', 'Email Failed'];

  constructor() {
    void this.loadAnalytics();
  }

  entries(value: Record<string, number>): [string, number][] {
    return Object.entries(value).slice(0, 6);
  }

  statusCount(status: string): number {
    return this.analytics()?.by_status[status] ?? this.store.statusCounts()[status] ?? 0;
  }

  pendingOffline(): number {
    const stats = this.store.offline.stats();
    return (
      stats.pendingReports +
      stats.pendingPhotos +
      stats.pendingDeletions +
      stats.pendingDeliveries
    );
  }

  sectionProgress(report: TechnicalReport): number {
    let complete = 0;
    if (report.customerName && report.branch) complete += 1;
    if (report.photos.length >= 16) complete += 1;
    if (report.brand && report.dot && report.serialNumber) complete += 1;
    return complete;
  }

  statusLabel(value: string): string {
    return value === 'Email Sent' ? 'Sent' : value === 'Email Failed' ? 'Failed' : value === 'Ready to Submit' ? 'Ready' : value;
  }

  private async loadAnalytics(): Promise<void> {
    try {
      this.analytics.set(await this.store.analytics());
    } catch {
      this.analytics.set(null);
    }
  }

  greeting(): string {
    const hour = new Date().getHours();
    return hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : 'evening';
  }

  statusClass(value: string): string {
    return value.toLowerCase().replaceAll(' ', '-');
  }
}
