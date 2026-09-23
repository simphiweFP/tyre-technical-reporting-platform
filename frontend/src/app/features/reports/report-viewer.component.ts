import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuditEvent, SystemAdminService } from '../../core/admin/system-admin.service';
@Component({selector:'app-report-viewer',imports:[FormsModule],templateUrl:'./report-viewer.component.html',styleUrl:'./operations.component.scss'})
export class ReportViewerComponent{private readonly admin=inject(SystemAdminService);readonly items=signal<AuditEvent[]>([]);readonly total=signal(0);readonly query=signal('');readonly days=signal(7);readonly message=signal('');constructor(){void this.load()}async load(){try{const r=await this.admin.auditEvents(this.query(),this.days());this.items.set(r.items);this.total.set(r.total)}catch{this.message.set('Audit activity could not be loaded.')}}details(item:AuditEvent){return Object.entries(item.details).map(([k,v])=>`${k}: ${v}`).join(', ')||item.entity_type}}
