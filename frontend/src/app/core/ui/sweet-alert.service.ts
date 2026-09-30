import { Injectable } from '@angular/core';

type SweetAlertIcon = 'success' | 'error' | 'warning' | 'info' | 'question';

declare const Swal: {
  fire(options: Record<string, unknown>): Promise<{ isConfirmed: boolean }>;
  showLoading(): void;
  close(): void;
};

@Injectable({ providedIn: 'root' })
export class SweetAlertService {
  async confirm(
    title: string,
    text: string,
    confirmButtonText = 'Continue',
    icon: SweetAlertIcon = 'question',
    danger = false,
  ): Promise<boolean> {
    const result = await Swal.fire({
      title,
      text,
      icon,
      showCancelButton: true,
      confirmButtonText,
      cancelButtonText: 'Cancel',
      reverseButtons: true,
      focusCancel: danger,
      confirmButtonColor: danger ? '#d71920' : '#2f3398',
      cancelButtonColor: '#667085',
      customClass: {
        popup: 'royal-swal',
        confirmButton: 'royal-swal-confirm',
        cancelButton: 'royal-swal-cancel',
      },
    });
    return result.isConfirmed;
  }

  async confirmReportSend(recipient: string, claimReference: string): Promise<boolean> {
    const result = await Swal.fire({
      title: 'Send technical report?',
      html: `<div style="text-align:left;line-height:1.55">
        <p style="margin:0 0 10px">You are about to send <strong>${claimReference}</strong>.</p>
        <p style="margin:0;color:#687078">Recipient: <strong>${recipient}</strong></p>
      </div>`,
      icon: 'question',
      showCancelButton: true,
      confirmButtonText: 'Send report',
      cancelButtonText: 'Not yet',
      reverseButtons: true,
      confirmButtonColor: '#2f3398',
      cancelButtonColor: '#667085',
      customClass: {
        popup: 'royal-swal',
        confirmButton: 'royal-swal-confirm',
        cancelButton: 'royal-swal-cancel',
      },
    });
    return result.isConfirmed;
  }

  loading(title: string, text: string): void {
    void Swal.fire({
      title,
      text,
      allowOutsideClick: false,
      allowEscapeKey: false,
      showConfirmButton: false,
      didOpen: () => Swal.showLoading(),
      customClass: { popup: 'royal-swal' },
    });
  }

  sending(
    title = 'Sending report…',
    text = 'Please wait while the report is being delivered.',
  ): void {
    this.loading(title, text);
  }

  close(): void {
    Swal.close();
  }

  success(title: string, text: string): Promise<{ isConfirmed: boolean }> {
    return Swal.fire({
      title,
      text,
      icon: 'success',
      confirmButtonText: 'Done',
      confirmButtonColor: '#2f3398',
      customClass: { popup: 'royal-swal' },
    });
  }

  info(title: string, text: string): Promise<{ isConfirmed: boolean }> {
    return Swal.fire({
      title,
      text,
      icon: 'info',
      confirmButtonText: 'OK',
      confirmButtonColor: '#2f3398',
      customClass: { popup: 'royal-swal' },
    });
  }

  warning(title: string, text: string): Promise<{ isConfirmed: boolean }> {
    return Swal.fire({
      title,
      text,
      icon: 'warning',
      confirmButtonText: 'OK',
      confirmButtonColor: '#d71920',
      customClass: { popup: 'royal-swal' },
    });
  }

  error(title: string, text: string): Promise<{ isConfirmed: boolean }> {
    return Swal.fire({
      title,
      text,
      icon: 'error',
      confirmButtonText: 'Try again',
      confirmButtonColor: '#d71920',
      customClass: { popup: 'royal-swal' },
    });
  }
}
