import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
interface Recipient {
  company: string;
  contact: string;
  email: string;
  cc: string;
  active: boolean;
}
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
              ><span>{{ item.contact }}</span>
            </div>
            <div>
              <strong>{{ item.email }}</strong
              ><span>{{ item.cc ? 'CC: ' + item.cc : 'No default CC' }}</span>
            </div>
            <span class="active" [class.off]="!item.active">{{
              item.active ? 'Active' : 'Inactive'
            }}</span
            ><button class="more" aria-label="Recipient options">•••</button>
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
  readonly showForm = signal(false);
  readonly query = signal('');
  readonly recipients = signal<Recipient[]>([
    {
      company: 'Manufacturer Claims Desk',
      contact: 'Claims Department',
      email: 'claims@example.co.za',
      cc: '',
      active: true,
    },
    {
      company: 'Fleet Partner',
      contact: 'Fleet Operations',
      email: 'fleet@example.co.za',
      cc: 'manager@example.co.za',
      active: true,
    },
  ]);
  newRecipient = { company: '', contact: '', email: '', cc: '' };
  filtered(): Recipient[] {
    const q = this.query().toLowerCase();
    return this.recipients().filter(
      (r) => !q || `${r.company} ${r.email} ${r.contact}`.toLowerCase().includes(q),
    );
  }
  addRecipient(): void {
    if (!this.newRecipient.company || !this.newRecipient.email) return;
    this.recipients.update((v) => [...v, { ...this.newRecipient, active: true }]);
    this.newRecipient = { company: '', contact: '', email: '', cc: '' };
    this.showForm.set(false);
  }
}
