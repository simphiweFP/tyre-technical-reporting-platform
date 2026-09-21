import { Component, computed, inject } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { ReportStore } from '../../core/data/report.store';
@Component({
  selector: 'app-dashboard',
  imports: [DatePipe, RouterLink],
  template: `
    <section class="page">
      <header class="page-header">
        <div>
          <p class="eyebrow">Operations overview</p>
          <h1>Good {{ greeting() }}, {{ firstName() }}</h1>
          <p>Continue a report or start a new tyre inspection.</p>
        </div>
        @if (canCapture()) {
          <a class="button primary" routerLink="/reports/new">＋ New technical report</a>
        }
      </header>
      <div class="metric-grid">
        <article class="metric card">
          <span class="metric-icon dark">▤</span>
          <div>
            <p>Total reports</p>
            <strong>{{ store.reports().length }}</strong
            ><small>Stored on this device</small>
          </div>
        </article>
        <article class="metric card">
          <span class="metric-icon amber">◷</span>
          <div>
            <p>Drafts in progress</p>
            <strong>{{ store.drafts().length }}</strong
            ><small>Ready to continue</small>
          </div>
        </article>
        <article class="metric card">
          <span class="metric-icon green">✓</span>
          <div>
            <p>Completed</p>
            <strong>{{ completed() }}</strong
            ><small>Submitted or emailed</small>
          </div>
        </article>
      </div>
      <div class="content-grid">
        <section class="card recent">
          <div class="section-head">
            <div>
              <h2>Recent reports</h2>
              <p>Your latest technical report activity</p>
            </div>
            <a routerLink="/reports">View all</a>
          </div>
          @if (recent().length) {
            <div class="report-list">
              @for (report of recent(); track report.id) {
                <a [routerLink]="['/reports', report.id, 'edit']" class="report-row"
                  ><div class="report-symbol">
                    {{ report.customerName ? report.customerName[0] : 'T' }}
                  </div>
                  <div class="report-main">
                    <strong>{{ report.claimReference }}</strong
                    ><span
                      >{{ report.customerName || 'Customer not captured' }} ·
                      {{ report.brand || 'Tyre details pending' }}</span
                    >
                  </div>
                  <span class="status" [class]="statusClass(report.status)">{{
                    report.status
                  }}</span
                  ><time>{{ report.updatedAt | date: 'd MMM, HH:mm' }}</time
                  ><span class="chevron">›</span></a
                >
              }
            </div>
          } @else {
            <div class="empty">
              <div>▤</div>
              <h3>No reports yet</h3>
              <p>Your first technical report will appear here.</p>
              @if (canCapture()) {
                <a class="button secondary" routerLink="/reports/new">Start first report</a>
              }
            </div>
          }
        </section>
        <aside class="card quick">
          <h2>Capture checklist</h2>
          <p>A complete report needs these essentials.</p>
          <ul>
            <li>
              <span>1</span>
              <div>
                <strong>Claim information</strong
                ><small>Customer, invoice and inspection details</small>
              </div>
            </li>
            <li>
              <span>2</span>
              <div>
                <strong>Tyre information</strong><small>DOT, serial, size and condition</small>
              </div>
            </li>
            <li>
              <span>3</span>
              <div>
                <strong>Guided photographs</strong
                ><small>Every required angle, clearly captured</small>
              </div>
            </li>
          </ul>
        </aside>
      </div>
    </section>
  `,
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent {
  readonly auth = inject(AuthService);
  readonly store = inject(ReportStore);
  readonly firstName = computed(() => this.auth.user()?.full_name.split(' ')[0] ?? 'there');
  readonly canCapture = computed(() => this.auth.hasRole('administrator', 'report_capturer'));
  readonly recent = computed(() => this.store.reports().slice(0, 5));
  readonly completed = computed(
    () =>
      this.store.reports().filter((r) => !['Draft', 'Ready to Submit'].includes(r.status)).length,
  );
  greeting(): string {
    const hour = new Date().getHours();
    return hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : 'evening';
  }
  statusClass(value: string): string {
    return value.toLowerCase().replaceAll(' ', '-');
  }
}
