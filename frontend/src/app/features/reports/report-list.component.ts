import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { ReportStore } from '../../core/data/report.store';

@Component({selector:'app-report-list',imports:[DatePipe,FormsModule,RouterLink],templateUrl:'./report-list.component.html',styleUrl:'./report-list.component.scss'})
export class ReportListComponent{
  readonly store=inject(ReportStore);readonly auth=inject(AuthService);readonly query=signal('');readonly status=signal('');readonly canCapture=computed(()=>this.auth.hasRole('administrator','report_capturer'));
  readonly filtered=computed(()=>{const q=this.query().trim().toLowerCase();return this.store.reports().filter(r=>(!this.status()||r.status===this.status())&&(!q||[r.claimReference,r.customerName,r.serialNumber,r.brand,r.branch].some(v=>v.toLowerCase().includes(q))))});
  statusLabel(value:string){return value==='Email Sent'?'Sent':value==='Email Failed'?'Failed':value==='Ready to Submit'?'Ready':value}
  statusClass(value:string){return value.toLowerCase().replaceAll(' ','-')}
}
