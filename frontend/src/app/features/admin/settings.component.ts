import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { OfflineDataService } from '../../core/offline/offline-data.service';
import { SweetAlertService } from '../../core/ui/sweet-alert.service';

@Component({
  selector: 'app-settings',
  imports: [DatePipe],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.scss',
})
export class SettingsComponent {
  readonly offline = inject(OfflineDataService);
  private readonly alerts = inject(SweetAlertService);
  readonly message = signal('');

  async syncNow(): Promise<void> {
    if (!this.offline.online()) {
      const message = 'This device is offline. Sync will start automatically when the connection returns.';
      this.message.set(message);
      await this.alerts.warning('Offline', message);
      return;
    }
    this.message.set('');
    this.alerts.loading('Syncing…', 'Uploading pending reports, photos and queued emails.');
    await this.offline.syncNow();
    this.alerts.close();
    const stats = this.offline.stats();
    const resultMessage = stats.conflicts
      ? `${stats.conflicts} report conflict(s) need review before they can sync.`
      : stats.pendingReports +
            stats.pendingPhotos +
            stats.pendingDeletions +
            stats.pendingDeliveries ===
          0
        ? 'All offline changes are synced.'
        : 'Some offline changes are still waiting to sync.';
    this.message.set(resultMessage);
    if (stats.conflicts) await this.alerts.warning('Sync needs attention', resultMessage);
    else await this.alerts.success('Sync complete', resultMessage);
  }

  async clearReferenceCache(): Promise<void> {
    if (!(await this.alerts.confirm(
      'Clear cached dropdown data?',
      'Pending reports and photos will stay safe. Only cached reference data will be cleared.',
      'Clear cache',
      'warning',
    ))) return;
    await this.offline.clearReferenceCache();
    const message = 'Cached dropdown data cleared. Pending reports and photos were not deleted.';
    this.message.set(message);
    await this.alerts.success('Cache cleared', message);
  }
}
