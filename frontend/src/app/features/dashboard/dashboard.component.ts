import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { ReportAnalytics, ReportStore } from '../../core/data/report.store';
import { TechnicalReport } from '../../shared/models/report.models';

@Component({
  selector: 'app-dashboard',
  imports: [DatePipe, RouterLink],
  template: `
    <section class="page role-dashboard">
      <header class="page-header">
        <div>
          <p class="eyebrow">{{ isAdmin() ? 'Operations overview' : isViewer() ? 'Reporting review' : 'My work queue' }}</p>
          <h1>Good {{ greeting() }}, {{ firstName() }}</h1>
          <p>
            {{
              isAdmin()
                ? 'See what needs attention across the reporting operation.'
                : isViewer()
                  ? 'Review recent technical reports and their audit history.'
                  : 'Continue your own reports and move ready work forward.'
            }}
          </p>
        </div>
        @if (canCapture()) {
          <a class="button primary" routerLink="/reports/new">＋ New technical report</a>
        }
      </header>

      @if (isCapturer()) {
        <div class="work-layout">
          <main>
            <section class="card continue-card">
              <div class="section-head">
                <div>
                  <h2>Continue where you left off</h2>
                  <p>Your most recently updated draft</p>
                </div>
                <a routerLink="/reports">View my claims</a>
              </div>
              @if (latestDraft(); as draft) {
                <a [routerLink]="['/reports', draft.id, 'edit']" class="continue-report">
                  <div>
                    <span class="work-kicker">DRAFT</span>
                    <h3>{{ draft.claimReference }}</h3>
                    <p>{{ draft.customerName || 'Customer still required' }}</p>
                  </div>
                  <div class="progress-copy">
                    <strong>{{ sectionProgress(draft) }}/3</strong>
                    <span>sections complete</span>
                  </div>
                  <div class="continue-action">Continue →</div>
                </a>
              } @else {
                <div class="empty compact-empty">
                  <h3>No draft waiting</h3>
                  <p>Start a new technical report when you are ready.</p>
                </div>
              }
            </section>

            <section class="card recent">
              <div class="section-head">
                <div><h2>My recent work</h2><p>Only claims created by you</p></div>
                <a routerLink="/reports">View all</a>
              </div>
              <div class="report-list">
                @for (report of recent(); track report.id) {
                  <a [routerLink]="report.status === 'Draft' ? ['/reports', report.id, 'edit'] : ['/reports', report.id]" class="report-row">
                    <div class="report-symbol">{{ report.customerName ? report.customerName[0] : 'T' }}</div>
                    <div class="report-main">
                      <strong>{{ report.claimReference }}</strong>
                      <span>{{ report.customerName || 'Customer not captured' }} · {{ report.brand || 'Tyre details pending' }}</span>
                    </div>
                    <span class="status" [class]="statusClass(report.status)">{{ report.status }}</span>
                    <time>{{ report.updatedAt | date: 'd MMM, HH:mm' }}</time>
                    <span class="chevron">›</span>
                  </a>
                } @empty {
                  <div class="empty compact-empty"><p>No claims created yet.</p></div>
                }
              </div>
            </section>
          </main>

          <aside class="work-side">
            <section class="card attention-card">
              <h2>Needs attention</h2>
              <p>What should move next</p>
              <a routerLink="/reports">
                <span class="attention-dot amber"></span>
                <div><strong>{{ statusCount('Draft') }}</strong><small>Drafts to continue</small></div>
              </a>
              <a routerLink="/reports">
                <span class="attention-dot blue"></span>
                <div><strong>{{ statusCount('Ready to Submit') }}</strong><small>Ready to submit</small></div>
              </a>
              <a routerLink="/delivery-centre">
                <span class="attention-dot red"></span>
                <div><strong>{{ statusCount('Email Failed') }}</strong><small>Delivery failures</small></div>
              </a>
              <div class="attention-row">
                <span class="attention-dot cloud">☁</span>
                <div><strong>{{ pendingOffline() }}</strong><small>Offline changes waiting</small></div>
              </div>
            </section>
            <a class="card audit-shortcut" routerLink="/audit-viewer">
              <span>▣</span>
              <div><strong>My claim history</strong><small>See who changed what and when</small></div>
              <b>›</b>
            </a>
          </aside>
        </div>
      } @else if (isAdmin()) {
        <section class="admin-attention">
          <div class="section-label"><h2>Needs attention</h2><p>Exceptions before routine totals</p></div>
          <div class="attention-grid">
            <a class="card attention-tile" routerLink="/reports"><strong>{{ statusCount('Draft') }}</strong><span>Drafts still open</span><small>Review work that has not moved forward</small></a>
            <a class="card attention-tile" routerLink="/reports"><strong>{{ statusCount('Ready to Submit') }}</strong><span>Ready to submit</span><small>Completed capture waiting for submission</small></a>
            <a class="card attention-tile danger" routerLink="/delivery-centre"><strong>{{ analytics()?.email_failed ?? 0 }}</strong><span>Email failures</span><small>Delivery issues requiring attention</small></a>
            <a class="card attention-tile" routerLink="/admin/settings"><strong>{{ pendingOffline() }}</strong><span>Offline changes</span><small>Waiting on this device to synchronize</small></a>
          </div>
        </section>

        <div class="admin-work-grid">
          <section class="card workflow-card">
            <div class="section-head"><div><h2>Workflow</h2><p>Where reports are in the process</p></div><a routerLink="/reports">Open claims</a></div>
            <div class="workflow-list">
              @for (status of workflowStatuses; track status) {
                <div><span>{{ statusLabel(status) }}</span><strong>{{ statusCount(status) }}</strong></div>
              }
            </div>
          </section>
          <section class="card branch-card">
            <div class="section-head"><div><h2>Branch workload</h2><p>Active report volume by branch</p></div></div>
            <div class="workflow-list">
              @for (item of entries(analytics()?.by_branch ?? {}); track item[0]) {
                <div><span>{{ item[0] }}</span><strong>{{ item[1] }}</strong></div>
              } @empty {
                <div><span>No branch activity</span><strong>0</strong></div>
              }
            </div>
          </section>
        </div>

        <section class="card recent">
          <div class="section-head"><div><h2>Recent claim activity</h2><p>Latest reports across the operation</p></div><a routerLink="/reports">View all</a></div>
          <div class="report-list">
            @for (report of recent(); track report.id) {
              <a [routerLink]="['/reports', report.id]" class="report-row">
                <div class="report-symbol">{{ report.customerName ? report.customerName[0] : 'T' }}</div>
                <div class="report-main"><strong>{{ report.claimReference }}</strong><span>{{ report.customerName || 'Customer not captured' }} · {{ report.branch || 'Branch not selected' }}</span></div>
                <span class="status" [class]="statusClass(report.status)">{{ report.status }}</span>
                <time>{{ report.updatedAt | date: 'd MMM, HH:mm' }}</time><span class="chevron">›</span>
              </a>
            }
          </div>
        </section>
      } @else if (isViewer()) {
        <div class="viewer-dashboard">
          <section class="card viewer-summary">
            <div><small>Reports available</small><strong>{{ analytics()?.total ?? store.total() }}</strong></div>
            <div><small>Submitted / emailed</small><strong>{{ analytics()?.completed ?? 0 }}</strong></div>
            <div><small>Ready for review</small><strong>{{ statusCount('Ready to Submit') }}</strong></div>
            <a routerLink="/audit-viewer">Open Audit Viewer →</a>
          </section>
          <section class="card recent">
            <div class="section-head"><div><h2>Recent technical reports</h2><p>Read-only reporting activity</p></div><a routerLink="/reports">View all</a></div>
            <div class="report-list">
              @for (report of recent(); track report.id) {
                <a [routerLink]="['/reports', report.id]" class="report-row">
                  <div class="report-symbol">{{ report.customerName ? report.customerName[0] : 'T' }}</div>
                  <div class="report-main"><strong>{{ report.claimReference }}</strong><span>{{ report.customerName || 'Customer not captured' }} · {{ report.brand || 'Tyre details pending' }}</span></div>
                  <span class="status" [class]="statusClass(report.status)">{{ report.status }}</span>
                  <time>{{ report.updatedAt | date: 'd MMM, HH:mm' }}</time><span class="chevron">›</span>
                </a>
              }
            </div>
          </section>
        </div>
      }
    </section>
  `,
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
    return stats.pendingReports + stats.pendingPhotos + stats.pendingDeletions;
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
