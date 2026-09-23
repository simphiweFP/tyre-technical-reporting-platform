import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ReportDeliveryService } from '../../core/delivery/report-delivery.service';
import { DeliveryAttempt } from '../../shared/models/report.models';
@Component({selector:'app-delivery-centre',imports:[FormsModule],templateUrl:'./delivery-centre.component.html',styleUrl:'./operations.component.scss'})
export class DeliveryCentreComponent{private readonly delivery=inject(ReportDeliveryService);readonly items=signal<DeliveryAttempt[]>([]);readonly total=signal(0);readonly query=signal('');readonly status=signal('');readonly message=signal('');constructor(){void this.load()}async load(){try{const r=await this.delivery.deliveries(this.query(),this.status());this.items.set(r.items);this.total.set(r.total)}catch{this.message.set('Delivery history could not be loaded.')}}async retry(id:string){await this.delivery.retry(id);await this.load()}clear(){this.query.set('');this.status.set('');void this.load()}}
