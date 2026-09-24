import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SystemAdminService, SystemSettings } from '../../core/admin/system-admin.service';

@Component({
  selector: 'app-settings',
  imports: [FormsModule],
  templateUrl: './settings.component.html',
  styleUrl: './admin.component.scss',
})
export class SettingsComponent {
  private readonly admin = inject(SystemAdminService);
  readonly settings = signal<SystemSettings | null>(null);
  readonly message = signal('');

  constructor() {
    void this.load();
  }

  async load(): Promise<void> {
    try {
      this.settings.set(await this.admin.settings());
    } catch {
      this.message.set('System settings could not be loaded.');
    }
  }

  async save(): Promise<void> {
    const value = this.settings();
    if (!value) return;
    try {
      this.settings.set(await this.admin.saveSettings(value));
      this.message.set('Settings saved successfully.');
    } catch {
      this.message.set('Settings could not be saved.');
    }
  }

  update<K extends keyof SystemSettings>(key: K, value: SystemSettings[K]): void {
    this.settings.update((settings) => (settings ? { ...settings, [key]: value } : settings));
  }
}
