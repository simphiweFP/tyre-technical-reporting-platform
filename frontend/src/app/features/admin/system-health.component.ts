import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { OperationsStatus, SystemAdminService } from '../../core/admin/system-admin.service';

@Component({
  selector: 'app-system-health',
  imports: [DatePipe],
  templateUrl: './system-health.component.html',
  styleUrl: './admin.component.scss',
})
export class SystemHealthComponent {
  private readonly admin = inject(SystemAdminService);
  readonly health = signal<OperationsStatus | null>(null);
  readonly message = signal('');
  readonly loading = signal(false);

  constructor() {
    void this.refresh();
  }

  async refresh(): Promise<void> {
    this.loading.set(true);
    this.message.set('');
    try {
      this.health.set(await this.admin.operations());
    } catch {
      this.message.set('Operational health could not be loaded.');
    } finally {
      this.loading.set(false);
    }
  }

  healthy(value: string): boolean {
    return value === 'healthy';
  }
}
