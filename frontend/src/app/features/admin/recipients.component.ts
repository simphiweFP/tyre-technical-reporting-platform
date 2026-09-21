import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ReportDeliveryService } from '../../core/delivery/report-delivery.service';
import { ReportRecipient } from '../../shared/models/report.models';
@Component({
  selector: 'app-recipients',
  imports: [FormsModule],
  template: `
    <section class="page">
      <header class="page-header">
        <div>
          <p class="eyebrow">Administration</p>
          <h1>Third-party recipients</h1>
          <p>Maintain the approved contacts who receive technical-report PDFs.</p>
        </div>
        <button class="button primary" (click)="showForm.set(true)">＋ Add recipient</button>
      </header>
      <section class="card list">
        <div class="list-head">
          <strong>{{ recipients().length }} recipients</strong
          ><label
            ><span>⌕</span><input [(ngModel)]="query" placeholder="Search company or email"
          /></label>
        </div>
        @for (item of filtered(); track item.email) {
          <article>
            <div class="company-icon">✉</div>
            <div class="person">
              <strong>{{ item.company }}</strong
              ><span>{{ item.contact_name }}</span>
            </div>
            <div>
              <strong>{{ item.email }}</strong
              ><span>{{ item.default_cc ? 'CC: ' + item.default_cc : 'No default CC' }}</span>
            </div>
            <span class="active" [class.off]="!item.is_active">{{
              item.is_active ? 'Active' : 'Inactive'
            }}</span
            ><button
              class="more"
              type="button"
              (click)="toggle(item)"
              [attr.aria-label]="'Toggle ' + item.company"
            >
              {{ item.is_active ? 'Disable' : 'Enable' }}
            </button>
          </article>
        }
      </section>
      @if (showForm()) {
        <div class="modal-backdrop" (click)="showForm.set(false)">
          <form class="modal card" (click)="$event.stopPropagation()" (ngSubmit)="addRecipient()">
            <div class="modal-head">
              <div>
                <p class="eyebrow">Delivery contact</p>
                <h2>Add recipient</h2>
              </div>
              <button type="button" (click)="showForm.set(false)">×</button>
            </div>
            <div class="field">
              <label>Company</label
              ><input name="company" [(ngModel)]="newRecipient.company" required />
            </div>
            <div class="field">
              <label>Contact person</label
              ><input name="contact" [(ngModel)]="newRecipient.contact" />
            </div>
            <div class="field">
              <label>Recipient email</label
              ><input name="email" [(ngModel)]="newRecipient.email" type="email" required />
            </div>
            <div class="field">
              <label>Default CC</label
              ><input name="cc" [(ngModel)]="newRecipient.cc" type="email" />
            </div>
            <button class="button primary" type="submit">Add recipient</button>
          </form>
        </div>
      }
    </section>
  `,
  styleUrl: './admin.component.scss',
})
export class RecipientsComponent {
  private readonly delivery = inject(ReportDeliveryService);
  readonly showForm = signal(false);
  readonly query = signal('');
  readonly recipients = signal<ReportRecipient[]>([]);
  newRecipient = { company: '', contact: '', email: '', cc: '' };
  constructor() {
    void this.load();
  }
  filtered(): ReportRecipient[] {
    const q = this.query().toLowerCase();
    return this.recipients().filter(
      (r) => !q || `${r.company} ${r.email} ${r.contact_name}`.toLowerCase().includes(q),
    );
  }
  async addRecipient(): Promise<void> {
    if (!this.newRecipient.company || !this.newRecipient.email) return;
    const created = await this.delivery.createRecipient({
      company: this.newRecipient.company,
      contact_name: this.newRecipient.contact,
      email: this.newRecipient.email,
      default_cc: this.newRecipient.cc || null,
    });
    this.recipients.update((items) => [...items, created]);
    this.newRecipient = { company: '', contact: '', email: '', cc: '' };
    this.showForm.set(false);
  }
  async toggle(recipient: ReportRecipient): Promise<void> {
    const updated = await this.delivery.setRecipientStatus(recipient.id, !recipient.is_active);
    this.recipients.update((items) =>
      items.map((item) => (item.id === updated.id ? updated : item)),
    );
  }
  private async load(): Promise<void> {
    this.recipients.set(await this.delivery.recipients(false));
  }
}
