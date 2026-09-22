import { Component, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ReportStore } from '../../core/data/report.store';

@Component({selector:'app-report-detail',templateUrl:'./report-detail.component.html',styleUrl:'./operations.component.scss'})
export class ReportDetailComponent{private readonly route=inject(ActivatedRoute);readonly store=inject(ReportStore);readonly id=this.route.snapshot.paramMap.get('id')??'';readonly report=this.store.get(this.id);readonly photos=[['Full view','/mock-tyre-full.jpg'],['Internal carcass 1','/mock-tyre-carcass.jpg'],['Tread depth 1','/mock-tread-depth.jpg'],['Tread pattern','/mock-tread-pattern.jpg'],['DOT','/mock-dot.jpg'],['Serial number','/mock-serial.jpg']]}
