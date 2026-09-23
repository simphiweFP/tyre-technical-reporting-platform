import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ReportStore } from '../../core/data/report.store';
import { ReportDeliveryService } from '../../core/delivery/report-delivery.service';
import { ReportIntelligenceService } from '../../core/media/report-intelligence.service';
import { ReportRecipient, TechnicalReport } from '../../shared/models/report.models';

@Component({selector:'app-report-detail',templateUrl:'./report-detail.component.html',styleUrl:'./operations.component.scss'})
export class ReportDetailComponent{
  private readonly route=inject(ActivatedRoute);private readonly router=inject(Router);private readonly store=inject(ReportStore);private readonly intelligence=inject(ReportIntelligenceService);private readonly delivery=inject(ReportDeliveryService);
  readonly report=signal<TechnicalReport|null>(null);readonly recipients=signal<ReportRecipient[]>([]);readonly selectedRecipient=signal('');readonly busy=signal('');readonly message=signal('');
  constructor(){void this.load()}
  async load(){try{const item=await this.store.loadOne(this.route.snapshot.paramMap.get('id')!);this.report.set(item)}catch{this.message.set('The report could not be loaded.');return}try{const recipients=await this.delivery.recipients();this.recipients.set(recipients);if(recipients.length)this.selectedRecipient.set(recipients[0].id)}catch{this.recipients.set([])}}
  async generatePdf(){const r=this.report();if(!r)return;this.busy.set('pdf');try{await this.intelligence.downloadPdf(r)}finally{this.busy.set('')}}
  async send(){const r=this.report();if(!r||!this.selectedRecipient())return;this.busy.set('send');try{await this.delivery.deliver(r,this.selectedRecipient());this.message.set('Report queued for delivery.');await this.load()}finally{this.busy.set('')}}
  async archive(){const r=this.report();if(!r)return;this.busy.set('archive');try{await this.store.archive(r.id);await this.router.navigate(['/reports'])}finally{this.busy.set('')}}
  photoUrl(category:string){return this.report()?.photos.find(p=>p.category===category)?.previewUrl||''}
}
