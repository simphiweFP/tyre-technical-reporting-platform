import { DatePipe, DecimalPipe, CurrencyPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import {
  ClaimsService,
  ClaimCase,
  ClaimData,
  ClaimOwner,
  AvailableReport,
  Supplier,
  ClaimMetrics,
  ClaimDelivery,
  ClaimActivity,
} from '../../core/claims/claims.service';
import { SweetAlertService } from '../../core/ui/sweet-alert.service';

@Component({
  selector: 'app-claims',
  imports: [FormsModule, DatePipe, DecimalPipe, CurrencyPipe, RouterLink],
  templateUrl: './claims.component.html',
  styleUrl: './claims.component.scss',
})
export class ClaimsComponent {
  readonly auth = inject(AuthService);
  private readonly api = inject(ClaimsService);
  private readonly alerts = inject(SweetAlertService);
  private readonly route = inject(ActivatedRoute);
  readonly tab = signal('tracker');
  readonly opening = signal(false);
  readonly expandedPanel = signal('');
  private listScrollY = 0;
  private detailRequest = 0;
  private handledHandover = '';
  readonly items = signal<ClaimCase[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly selected = signal<ClaimCase | null>(null);
  readonly owners = signal<ClaimOwner[]>([]);
  readonly available = signal<AvailableReport[]>([]);
  readonly suppliers = signal<Supplier[]>([]);
  readonly stats = signal<ClaimMetrics | null>(null);
  readonly deliveries = signal<ClaimDelivery[]>([]);
  readonly activity = signal<ClaimActivity[]>([]);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  readonly handoverOpen = signal(false);
  readonly sendOpen = signal(false);
  readonly workbookSend = signal(false);
  readonly canWrite = computed(() => this.auth.hasRole('claims_administrator'));
  readonly canHandover = computed(() => this.auth.hasRole('administrator', 'report_capturer'));
  readonly credits = computed(() =>
    this.items().filter(
      (i) => i.data.supplier_status === 'Accepted' || i.data.supplier_status === 'Rejected',
    ),
  );
  readonly pendingInstructions = computed(() =>
    this.items().flatMap((c) =>
      c.instructions
        .slice(0, 1)
        .filter((i) => !i.acknowledged_at)
        .map((i) => ({ claim: c, instruction: i })),
    ),
  );
  filters = {
    search: '',
    supplier: '',
    branch: '',
    decision: '',
    workflow_status: '',
    date_from: '',
    date_to: '',
  };
  form: ClaimData | null = null;
  workflowStatus = 'In progress';
  handover = { report_id: '', assigned_to: '', notes: '' };
  reassignment = '';
  instructionNotes = '';
  sendForm = { kind: 'tracker', email: '', cc: '', body: '', instruction_id: '' };
  importFile: File | null = null;
  importOwner = '';
  private searchTimer?: ReturnType<typeof setTimeout>;
  private supplierRequest = 0;
  private loadRequest = 0;
  selectTab(key: string): void {
    this.tab.set(key);
    this.offset.set(0);
    void this.load();
  }

  readonly tabs = [
    { key: 'tracker', label: 'Claim Tracker' },
    { key: 'credit', label: 'Instruction to Credit' },
    { key: 'scorecard', label: 'Supplier Scorecard' },
    { key: 'metrics', label: 'Other Metrics' },
  ];
  readonly sourceFields = [
    { label: 'Customer Invoice no.', key: 'customer_invoice_number' },
    { label: 'Branch', key: 'branch' },
    { label: 'Brand', key: 'brand' },
    { label: 'Tyre size', key: 'tyre_size' },
    { label: 'Pattern', key: 'pattern' },
    { label: 'Serial number', key: 'serial_number' },
  ];
  columns() {
    return [
      { label: 'Claim', key: 'claim_reference' },
      { label: 'Customer', key: 'customer_name' },
      { label: 'Supplier', key: 'supplier' },
      { label: 'Decision', key: 'supplier_status' },
      ...(this.tab() === 'credit'
        ? [{ label: '% to credit', key: 'customer_credit_percentage' }]
        : []),
      { label: 'Next action', key: 'next_action' },
      { label: 'Assigned to', key: 'owner_name' },
    ];
  }
  nextAction(item: ClaimCase): string {
    if (item.workflow_status === 'Closed') return 'Completed';
    if (item.instructions[0] && !item.instructions[0].acknowledged_at)
      return 'Receive credit instruction';
    if (!item.data.supplier) return 'Select supplier';
    if (item.data.supplier_status === 'Rejected') return 'Send rejection report';
    if (item.data.supplier_status === 'Under review')
      return item.data.supplier_submitted_date ? 'Await supplier feedback' : 'Send to supplier';
    if (item.data.customer_credit_percentage === null) return 'Enter credit percentage';
    if (item.credit_outstanding) return 'Pass customer credit';
    if (item.supplier_offset_outstanding) return 'Record supplier offset';
    return 'Close claim';
  }
  today(): string {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }
  referenceChanged(kind: string): void {
    if (!this.form) return;
    if (
      kind === 'customer' &&
      this.form.credit_note_reference.trim() &&
      !this.form.customer_credit_date
    )
      this.form.customer_credit_date = this.today();
    if (
      kind === 'supplier' &&
      this.form.supplier_offset_invoice.trim() &&
      !this.form.supplier_offset_date
    )
      this.form.supplier_offset_date = this.today();
  }
  cell(item: ClaimCase, key: string): string {
    if (key === 'next_action') return this.nextAction(item);
    if (key === 'supplier' && this.tab() === 'credit')
      return item.data.instruction_supplier || item.data.supplier || '—';
    const value =
      (item as unknown as Record<string, unknown>)[key] ??
      (item.data as unknown as Record<string, unknown>)[key];
    if (value === null || value === undefined || value === '')
      return key === 'credit_note_reference' && item.data.supplier_status === 'Rejected'
        ? 'Send rejection report'
        : '—';
    if (['remaining_percentage', 'accepted_percentage', 'customer_credit_percentage'].includes(key))
      return Number(value).toFixed(2) + '%';
    return String(value);
  }
  constructor() {
    void this.load();
  }
  activeFilters(metrics = false): Record<string, string> {
    const filters = Object.fromEntries(
      Object.entries(this.filters).filter(
        ([key, value]) =>
          value && (!metrics || ['supplier', 'branch', 'date_from', 'date_to'].includes(key)),
      ),
    );
    if (!metrics && this.tab() === 'credit') filters['credit_only'] = 'true';
    return filters;
  }
  async load(): Promise<void> {
    const request = ++this.loadRequest;
    this.busy.set(true);
    this.error.set('');
    try {
      const [list, stats, owners, suppliers] = await Promise.all([
        this.api.list(this.activeFilters(), this.offset()),
        this.api.metrics(this.activeFilters(true)),
        this.api.owners(),
        this.api.suppliers(),
      ]);
      if (request !== this.loadRequest) return;
      this.items.set(list.items);
      this.total.set(list.total);
      this.stats.set(stats);
      this.owners.set(owners);
      this.suppliers.set(suppliers.items);
      if (this.canHandover()) this.available.set(await this.api.available());
      const reportId = this.route.snapshot.queryParamMap.get('handover');
      if (reportId && this.handledHandover !== reportId) {
        this.handledHandover = reportId;
        try {
          await this.open(await this.api.forReport(reportId));
        } catch (e) {
          if (this.available().some((r) => r.id === reportId)) {
            this.handover.report_id = reportId;
            this.handoverOpen.set(true);
          } else this.error.set(this.message(e));
        }
      }
    } catch (e) {
      if (request === this.loadRequest) this.error.set(this.message(e));
    } finally {
      if (request === this.loadRequest) this.busy.set(false);
    }
  }
  clearFilters(): void {
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.filters = {
      search: '',
      supplier: '',
      branch: '',
      decision: '',
      workflow_status: '',
      date_from: '',
      date_to: '',
    };
    this.offset.set(0);
    void this.load();
  }
  search(): void {
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => {
      this.offset.set(0);
      void this.load();
    }, 300);
  }
  async page(direction: number) {
    this.offset.set(Math.max(0, this.offset() + direction * 100));
    await this.load();
  }
  async open(item: ClaimCase): Promise<void> {
    const request = ++this.detailRequest;
    this.error.set('');
    this.opening.set(true);
    if (!this.selected()) this.listScrollY = window.scrollY;
    try {
      const fresh = await this.api.get(item.id);
      if (request !== this.detailRequest) return;
      this.deliveries.set([]);
      this.activity.set([]);
      this.instructionNotes = '';
      this.apply(fresh);
      this.expandedPanel.set('');
      setTimeout(() => this.showSection('claims-management'));
      const [deliveries, activity] = await Promise.all([
        this.api.deliveries(fresh.claim_reference),
        this.api.activity(fresh.id),
      ]);
      if (request !== this.detailRequest) return;
      this.deliveries.set(deliveries);
      this.activity.set(activity);
    } catch (e) {
      if (request === this.detailRequest) this.error.set(this.message(e));
    } finally {
      if (request === this.detailRequest) this.opening.set(false);
    }
  }
  closeDetails(): void {
    ++this.detailRequest;
    this.opening.set(false);
    this.selected.set(null);
    this.form = null;
    this.error.set('');
    setTimeout(() => window.scrollTo({ top: this.listScrollY }));
  }
  togglePanel(id: string, event: Event): void {
    event.preventDefault();
    this.expandedPanel.update((current) => (current === id ? '' : id));
  }
  nextSection(item: ClaimCase): string {
    if (item.workflow_status === 'Closed') return '';
    if (item.instructions[0] && !item.instructions[0].acknowledged_at) return 'claim-documents';
    if (!item.data.supplier) return 'claim-information';
    if (item.data.supplier_status === 'Rejected') return 'claim-documents';
    if (item.data.supplier_status === 'Under review')
      return item.data.supplier_submitted_date ? 'claim-information' : 'claim-documents';
    if (item.data.customer_credit_percentage === null || item.credit_outstanding)
      return 'customer-credit';
    if (item.supplier_offset_outstanding) return 'supplier-recovery';
    return 'claim-information';
  }
  showSection(id: string): void {
    if (id !== 'claims-management') this.expandedPanel.set(id);
    setTimeout(() =>
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
    );
  }
  apply(item: ClaimCase): void {
    this.selected.set(item);
    this.form = structuredClone(item.data);
    this.workflowStatus = item.workflow_status;
    this.reassignment = item.assigned_to;
    this.items.update((items) => items.map((i) => (i.id === item.id ? item : i)));
  }
  async supplierSearch(name: string, instruction = false): Promise<void> {
    if (!this.form) return;
    if (instruction) this.form.instruction_supplier = name;
    else {
      this.form.supplier = name;
      this.form.supplier_code = '';
    }
    const request = ++this.supplierRequest;
    try {
      const result = await this.api.suppliers(name);
      if (request !== this.supplierRequest) return;
      this.suppliers.set(result.items);
      if (!instruction && this.form)
        this.form.supplier_code = result.items.find((i) => i.CardName === name)?.CardCode ?? '';
    } catch {
      this.error.set(
        'Supplier suggestions could not be loaded. You can still type the supplier name.',
      );
    }
  }
  remaining(): number | null {
    const rtd = this.form?.remaining_tread_depth;
    const otd = this.form?.original_tread_depth;
    return rtd !== null && rtd !== undefined && otd ? (rtd / otd) * 100 : null;
  }
  decisionChanged(): void {
    if (this.form?.supplier_status === 'Rejected') {
      this.form.accepted_percentage = 0;
      this.form.customer_credit_percentage = 0;
    }
    if (
      this.form &&
      this.form.supplier_status !== 'Under review' &&
      !this.form.supplier_feedback_date
    )
      this.form.supplier_feedback_date = this.today();
  }
  async save(form: NgForm): Promise<void> {
    const item = this.selected();
    if (!item || !this.form || !this.canWrite()) return;
    if (form.invalid) {
      form.control.markAllAsTouched();
      this.error.set('Complete the highlighted fields.');
      const invalidName = Object.keys(form.controls).find((name) => form.controls[name].invalid);
      const input = invalidName ? document.getElementsByName(invalidName)[0] : null;
      const card = input?.closest('details');
      if (card?.id) {
        this.showSection(card.id);
        setTimeout(() => input?.focus());
      }
      return;
    }
    const data = { ...this.form };
    for (const key of [
      'supplier_submitted_date',
      'supplier_feedback_date',
      'customer_credit_date',
      'supplier_offset_date',
    ] as const)
      data[key] ||= null;
    this.busy.set(true);
    this.error.set('');
    try {
      this.apply(
        await this.api.update(
          item,
          data,
          this.workflowStatus === 'Received' ? 'In progress' : this.workflowStatus,
        ),
      );
      await this.refreshMetrics();
      this.notice.set(
        data.supplier_status === 'Accepted' && data.customer_credit_percentage !== null
          ? 'Saved. The credit instruction is ready in the Claims Administrator inbox.'
          : 'Claim tracking saved.',
      );
      await this.alerts.success('Claim updated', item.claim_reference + ' was saved.');
    } catch (e) {
      this.error.set(this.message(e));
    } finally {
      this.busy.set(false);
    }
  }
  async handOver(): Promise<void> {
    if (!this.handover.report_id || !this.handover.assigned_to) return;
    this.busy.set(true);
    this.error.set('');
    try {
      const item = await this.api.handover(
        this.handover.report_id,
        this.handover.assigned_to,
        this.handover.notes,
      );
      this.handoverOpen.set(false);
      await this.load();
      await this.open(item);
      this.notice.set('Claim assigned to ' + item.owner_name);
    } catch (e) {
      this.error.set(this.message(e));
    } finally {
      this.busy.set(false);
    }
  }
  async reassign(): Promise<void> {
    const item = this.selected();
    if (!item) return;
    this.busy.set(true);
    this.error.set('');
    try {
      this.apply(
        await this.api.reassign(item.id, this.reassignment, 'Reassigned in Claims Management'),
      );
      this.notice.set('Claim owner updated.');
    } catch (e) {
      this.error.set(this.message(e));
    } finally {
      this.busy.set(false);
    }
  }
  async issue(): Promise<void> {
    const item = this.selected();
    if (!item) return;
    this.busy.set(true);
    this.error.set('');
    try {
      this.apply(
        await this.api.issue(item.id, item.data.instruction_supplier, this.instructionNotes),
      );
      this.notice.set('Credit instruction delivered to the Claims Administrator inbox.');
    } catch (e) {
      this.error.set(this.message(e));
    } finally {
      this.busy.set(false);
    }
  }
  async receive(item: ClaimCase, instruction: string): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      const updated = await this.api.receive(item.id, instruction);
      this.items.update((items) => items.map((i) => (i.id === updated.id ? updated : i)));
      if (this.selected()?.id === updated.id) this.apply(updated);
    } catch (e) {
      this.error.set(this.message(e));
    } finally {
      this.busy.set(false);
    }
  }
  async document(kind: string, instruction?: string): Promise<void> {
    const item = this.selected();
    if (!item) return;
    const prefixes: Record<string, string> = {
      technical: 'Technical_Report',
      tracker: 'Claim_Tracker',
      credit: 'Instruction_to_Credit',
      rejection: 'Rejection_Report',
    };
    this.busy.set(true);
    this.error.set('');
    try {
      await this.api.download(
        `${item.id}/documents/${kind}`,
        `${prefixes[kind]}_${item.claim_reference}.pdf`,
        instruction ? { instruction_id: instruction } : {},
      );
    } catch (e) {
      this.error.set(await this.downloadError(e));
    } finally {
      this.busy.set(false);
    }
  }
  prepareWorkbookEmail(section = this.tab()): void {
    this.prepareSend(section);
    this.workbookSend.set(true);
    this.sendForm.email = '';
  }
  prepareSend(kind: string, instruction?: string): void {
    this.workbookSend.set(false);
    this.sendForm = {
      kind,
      email: kind === 'credit' ? (this.selected()?.owner_email ?? '') : '',
      cc: '',
      body: '',
      instruction_id: instruction ?? '',
    };
    this.sendOpen.set(true);
  }
  async send(form: NgForm): Promise<void> {
    if (form.invalid) {
      form.control.markAllAsTouched();
      return;
    }
    const cc = this.sendForm.cc.split(/[,;\s]+/).filter(Boolean);
    if (cc.length > 5 || cc.some((e) => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e))) {
      this.error.set('Enter up to five valid CC addresses.');
      return;
    }
    this.busy.set(true);
    this.error.set('');
    try {
      const item = this.selected();
      const result = this.workbookSend()
        ? await this.api.sendWorkbook(
            this.sendForm.kind,
            this.activeFilters(true),
            this.sendForm.email,
            cc,
            this.sendForm.body,
          )
        : await this.api.send(
            item!.id,
            this.sendForm.kind,
            this.sendForm.email,
            cc,
            this.sendForm.body,
            this.sendForm.instruction_id || undefined,
          );
      this.sendOpen.set(false);
      if (item && !this.workbookSend())
        this.deliveries.set(await this.api.deliveries(item.claim_reference));
      if (result.status === 'Sent')
        await this.alerts.success(
          'Report accepted',
          'The mail server accepted the report. Delivery is recorded in Delivery Centre.',
        );
      else {
        this.error.set(
          result.error_message ||
            'Email could not be delivered. The attempt is recorded in Delivery Centre.',
        );
        await this.alerts.error('Email delivery failed', this.error());
      }
    } catch (e) {
      this.error.set(this.message(e));
    } finally {
      this.busy.set(false);
    }
  }
  async export(section: string): Promise<void> {
    this.error.set('');
    this.busy.set(true);
    try {
      await this.api.download(`export/${section}`, `${section}.csv`, this.activeFilters(true));
    } catch (e) {
      this.error.set(await this.downloadError(e));
    } finally {
      this.busy.set(false);
    }
  }
  async scorecardPdf(): Promise<void> {
    try {
      await this.api.download('scorecard/pdf', 'Supplier_Scorecard.pdf', this.activeFilters(true));
    } catch (e) {
      this.error.set(await this.downloadError(e));
    }
  }
  async importWorkbook(): Promise<void> {
    if (!this.importFile || !this.importOwner) return;
    this.busy.set(true);
    this.error.set('');
    try {
      const r = await this.api.import(this.importFile, this.importOwner);
      this.notice.set(
        `${r.imported} claims imported. ${r.skipped} skipped. ${r.warnings.join(' ')}`,
      );
      await this.load();
    } catch (e) {
      this.error.set(this.message(e));
    } finally {
      this.busy.set(false);
    }
  }
  fileChanged(event: Event): void {
    this.importFile = (event.target as HTMLInputElement).files?.[0] ?? null;
  }
  rank(values: { name: string; count: number }[]): string {
    return values.map((v) => `${v.name} (${v.count})`).join(', ') || 'No claims';
  }
  private async refreshMetrics() {
    this.stats.set(await this.api.metrics(this.activeFilters(true)));
  }
  private async downloadError(e: unknown): Promise<string> {
    if (e instanceof HttpErrorResponse && e.error instanceof Blob) {
      try {
        return JSON.parse(await e.error.text()).detail || 'Download failed.';
      } catch {
        return 'Download failed.';
      }
    }
    return this.message(e);
  }
  private message(e: unknown): string {
    if (e instanceof HttpErrorResponse) {
      const detail = e.error?.detail;
      if (typeof detail === 'string') return detail;
      if (Array.isArray(detail))
        return detail.map((d) => `${d.loc?.slice(1).join(' ')}: ${d.msg}`).join('. ');
      if (e.status === 0)
        return 'Connect to the network to manage claims. Your entered values are still on this screen.';
    }
    return 'The action could not be completed. Please try again.';
  }
}
