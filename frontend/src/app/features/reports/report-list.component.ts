import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Branch, UserAdminService } from '../../core/admin/user-admin.service';
import { AuthService } from '../../core/auth/auth.service';
import { ReportAnalytics, ReportStore } from '../../core/data/report.store';
import { ReportStatus } from '../../shared/models/report.models';

@Component({
  selector: 'app-report-list',
  imports: [DatePipe, FormsModule, RouterLink],
  templateUrl: './report-list.component.html',
  styleUrl: './report-list.component.scss',
})
export class ReportListComponent {
  readonly store = inject(ReportStore);
  readonly auth = inject(AuthService);
  private readonly admin = inject(UserAdminService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly query = signal(this.route.snapshot.queryParamMap.get('q') ?? '');
  readonly status = signal('');
  readonly branch = signal('');
  readonly dateFrom = signal('');
  readonly dateTo = signal('');
  readonly archived = signal(false);
  readonly page = signal(0);
  readonly pageSize = 20;
  readonly branches = signal<Branch[]>([]);
  readonly analytics = signal<ReportAnalytics | null>(null);
  readonly message = signal('');
  readonly canCapture = computed(() => this.auth.hasRole('administrator', 'report_capturer'));
  readonly canArchive = computed(() => this.auth.hasRole('administrator'));
  readonly pageCount = computed(() => Math.max(1, Math.ceil(this.store.total() / this.pageSize)));

  constructor() { void this.initialise(); }

  async initialise(): Promise<void> {
    const [branches, analytics] = await Promise.all([
      this.admin.branches().catch(() => []),
      this.store.analytics().catch(() => null),
    ]);
    this.branches.set(branches);
    this.analytics.set(analytics);
    await this.load();
  }

  async load(resetPage = false): Promise<void> {
    if (resetPage) this.page.set(0);
    this.message.set('');
    await this.router.navigate([], { relativeTo: this.route, queryParams: { q: this.query() || null }, replaceUrl: true });
    try {
      await this.store.refresh({ query: this.query(), status: this.status(), branch: this.branch(), dateFrom: this.dateFrom(), dateTo: this.dateTo(), archived: this.archived(), offset: this.page() * this.pageSize, limit: this.pageSize });
    } catch {
      this.message.set('Claims could not be loaded. Check the API connection.');
    }
  }

  selectStatus(value: string, archived = false): void { this.status.set(value); this.archived.set(archived); void this.load(true); }
  clear(): void { this.query.set(''); this.status.set(''); this.branch.set(''); this.dateFrom.set(''); this.dateTo.set(''); this.archived.set(false); void this.load(true); }
  previous(): void { if (this.page() === 0) return; this.page.update((value) => value - 1); void this.load(); }
  next(): void { if (this.page() + 1 >= this.pageCount()) return; this.page.update((value) => value + 1); void this.load(); }
  async archiveReport(id: string): Promise<void> { await this.store.archive(id); await this.load(); this.analytics.set(await this.store.analytics()); }
  count(status?: ReportStatus): number { const summary = this.analytics(); if (!summary) return 0; return status ? (summary.by_status[status] ?? 0) : summary.total; }
  statusLabel(value: string): string { return value === 'Email Sent' ? 'Sent' : value === 'Email Failed' ? 'Failed' : value === 'Ready to Submit' ? 'Ready' : value; }
  statusClass(value: string): string { return value.toLowerCase().replaceAll(' ', '-'); }
}
