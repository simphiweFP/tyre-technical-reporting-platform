import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Branch, ManagedUser, UserAdminService } from '../../core/admin/user-admin.service';
import { UserRole } from '../../shared/models/auth.models';

@Component({selector:'app-users',imports:[FormsModule],templateUrl:'./users.component.html',styleUrl:'./admin.component.scss'})
export class UsersComponent {
  private readonly admin=inject(UserAdminService);
  readonly showForm=signal(false); readonly query=signal(''); readonly users=signal<ManagedUser[]>([]); readonly branches=signal<Branch[]>([]); readonly notice=signal('');
  newUser:{email:string;full_name:string;job_title:string;role:UserRole;branch_id:string|null}={email:'',full_name:'',job_title:'',role:'report_capturer',branch_id:null};
  constructor(){void this.load()}
  filtered(){const q=this.query().toLowerCase();return this.users().filter(u=>!q||`${u.full_name} ${u.email} ${u.role}`.toLowerCase().includes(q))}
  username(user:ManagedUser){return user.email.split('@')[0]}
  roleLabel(role:string){return role.replace('_',' ').replace(/\b\w/g,v=>v.toUpperCase())}
  branchName(id:string|null){return this.branches().find(b=>b.id===id)?.name??'All Branches'}
  async addUser(){if(!this.newUser.full_name||!this.newUser.email)return;const created=await this.admin.create({...this.newUser,job_title:this.newUser.job_title||null});this.users.update(x=>[...x,created]);this.notice.set(`User created. Temporary password: ${created.temporary_password}`);this.showForm.set(false)}
  async toggle(user:ManagedUser){const updated=await this.admin.update(user.id,{is_active:!user.is_active});this.replace(updated)}
  async changeRole(user:ManagedUser,role:UserRole){this.replace(await this.admin.update(user.id,{role}))}
  async changeBranch(user:ManagedUser,branch_id:string|null){this.replace(await this.admin.update(user.id,{branch_id}))}
  async reset(user:ManagedUser){const r=await this.admin.resetPassword(user.id);this.notice.set(`Temporary password for ${user.full_name}: ${r.temporary_password}`)}
  private async load(){const [u,b]=await Promise.all([this.admin.users(),this.admin.branches()]);this.users.set(u);this.branches.set(b)}
  private replace(user:ManagedUser){this.users.update(x=>x.map(i=>i.id===user.id?user:i))}
}
