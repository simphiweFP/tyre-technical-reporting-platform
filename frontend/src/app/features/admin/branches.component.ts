import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Branch, UserAdminService } from '../../core/admin/user-admin.service';

@Component({selector:'app-branches',imports:[FormsModule],templateUrl:'./branches.component.html',styleUrl:'./admin.component.scss'})
export class BranchesComponent{private readonly admin=inject(UserAdminService);readonly branches=signal<Branch[]>([]);readonly query=signal('');constructor(){void this.load()}filtered(){const q=this.query().toLowerCase();return this.branches().filter(b=>!q||`${b.name} ${b.code}`.toLowerCase().includes(q))}private async load(){this.branches.set(await this.admin.branches())}}
