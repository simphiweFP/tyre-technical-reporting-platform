import { Injectable } from '@angular/core';

declare const Swal: {
  fire(options: Record<string, unknown>): Promise<{ isConfirmed: boolean }>;
  showLoading(): void;
  close(): void;
};

@Injectable({ providedIn: 'root' })
export class SweetAlertService {
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
      focusCancel: true,
      confirmButtonColor: '#d71920',
      cancelButtonColor: '#667085',
      customClass: {
        popup: 'royal-swal',
        confirmButton: 'royal-swal-confirm',
        cancelButton: 'royal-swal-cancel',
      },
    });
    return result.isConfirmed;
  }

  sending(title = 'Sending report…', text = 'Please wait while the report is being delivered.'): void {
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

  close(): void {
    Swal.close();
  }

  success(title: string, text: string): Promise<{ isConfirmed: boolean }> {
    return Swal.fire({
      title,
      text,
      icon: 'success',
      confirmButtonText: 'Done',
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
