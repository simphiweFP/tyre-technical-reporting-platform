import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ReportDeliveryService } from '../../core/delivery/report-delivery.service';
import { ReportRecipient } from '../../shared/models/report.models';

@Component({selector:'app-recipients',imports:[FormsModule],templateUrl:'./recipients.component.html',styleUrl:'./admin.component.scss'})
export class RecipientsComponent {
  private readonly delivery=inject(ReportDeliveryService);readonly showForm=signal(false);readonly query=signal('');readonly recipients=signal<ReportRecipient[]>([]);newRecipient={company:'',contact:'',email:'',cc:''};
  constructor(){void this.load()}
  filtered(){const q=this.query().toLowerCase();return this.recipients().filter(r=>!q||`${r.company} ${r.email}`.toLowerCase().includes(q))}
  async addRecipient(){if(!this.newRecipient.company||!this.newRecipient.email)return;const r=await this.delivery.createRecipient({company:this.newRecipient.company,contact_name:this.newRecipient.contact,email:this.newRecipient.email,default_cc:this.newRecipient.cc||null});this.recipients.update(x=>[...x,r]);this.showForm.set(false)}
  async toggle(item:ReportRecipient){const r=await this.delivery.setRecipientStatus(item.id,!item.is_active);this.recipients.update(x=>x.map(i=>i.id===r.id?r:i))}
  private async load(){this.recipients.set(await this.delivery.recipients(false))}
}
