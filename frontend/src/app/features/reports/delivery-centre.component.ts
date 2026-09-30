import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  DeliveryDetail,
  ReportDeliveryService,
} from '../../core/delivery/report-delivery.service';
import { DeliveryAttempt } from '../../shared/models/report.models';
@Component({selector:'app-delivery-centre',imports:[CommonModule,FormsModule],templateUrl:'./delivery-centre.component.html',styleUrl:'./operations.component.scss'})
export class DeliveryCentreComponent{
  private readonly delivery=inject(ReportDeliveryService);
  readonly items=signal<DeliveryAttempt[]>([]);
  readonly total=signal(0);
  readonly query=signal('');
  readonly status=signal('');
  readonly message=signal('');
  readonly selected=signal<DeliveryDetail|null>(null);
  readonly detailsBusy=signal(false);

  constructor(){void this.load()}

  async load(){
    try{
      const r=await this.delivery.deliveries(this.query(),this.status());
      this.items.set(r.items);
      this.total.set(r.total);
    }catch{
      this.message.set('Delivery history could not be loaded.');
    }
  }

  async retry(id:string){
    this.message.set('');
    try{
      const result=await this.delivery.retry(id);
      this.message.set(result.status==='Sent'?'Email resent successfully.':'Email resend attempted.');
      await this.load();
      if(this.selected()?.id===id) await this.view(id);
    }catch{
      this.message.set('Email could not be resent. Open the delivery to view the latest error.');
      await this.load();
    }
  }

  async view(id:string){
    this.detailsBusy.set(true);
    try{
      this.selected.set(await this.delivery.deliveryDetails(id));
    }catch{
      this.message.set('Delivery details could not be loaded.');
    }finally{
      this.detailsBusy.set(false);
    }
  }

  closeDetails(){this.selected.set(null)}

  viewPdf(id:string){this.delivery.openDeliveryPdf(id)}

  async remove(id:string){
    if(!window.confirm('Remove this delivery record from the active Delivery Centre? This is a soft delete.')) return;
    try{
      await this.delivery.softDeleteDelivery(id);
      if(this.selected()?.id===id) this.closeDetails();
      this.message.set('Delivery record removed from the active list.');
      await this.load();
    }catch{
      this.message.set('Delivery record could not be removed.');
    }
  }

  clear(){this.query.set('');this.status.set('');void this.load()}
}
