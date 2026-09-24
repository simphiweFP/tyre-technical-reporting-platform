import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { OfflineDataService } from '../../core/offline/offline-data.service';

@Component({
  selector: 'app-settings',
  imports: [DatePipe],
  templateUrl: './settings.component.html',
  styleUrl: './admin.component.scss',
})
export class SettingsComponent {
  readonly offline = inject(OfflineDataService);
  readonly message = signal('');

  async syncNow(): Promise<void> {
    if (!this.offline.online()) {
      this.message.set('This device is offline. Sync will start automatically when the connection returns.');
      return;
    }
    this.message.set('');
    await this.offline.syncNow();
    const stats = this.offline.stats();
    this.message.set(
      stats.conflicts
        ? `${stats.conflicts} report conflict(s) need review before they can sync.`
        : stats.pendingReports + stats.pendingPhotos + stats.pendingDeletions === 0
          ? 'All offline changes are synced.'
          : 'Some offline changes are still waiting to sync.',
    );
  }

  async clearReferenceCache(): Promise<void> {
    await this.offline.clearReferenceCache();
    this.message.set('Cached dropdown data cleared. Pending reports and photos were not deleted.');
  }
}
