import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ImageAnalysisResponse, TechnicalReport } from '../../shared/models/report.models';

export interface OptimizedImage {
  blob: Blob;
  previewUrl: string;
  sha256: string;
}

@Injectable({ providedIn: 'root' })
export class ReportIntelligenceService {
  private readonly http = inject(HttpClient);

  async optimize(file: File): Promise<OptimizedImage> {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext('2d')?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    const blob = await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob(
        (result) => (result ? resolve(result) : reject(new Error('Image compression failed'))),
        'image/jpeg',
        0.82,
      ),
    );
    const bytes = await blob.arrayBuffer();
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    const sha256 = [...new Uint8Array(digest)]
      .map((value) => value.toString(16).padStart(2, '0'))
      .join('');
    const previewUrl = await this.asDataUrl(blob);
    return { blob, previewUrl, sha256 };
  }

  analyse(blob: Blob, filename: string): Promise<ImageAnalysisResponse> {
    const body = new FormData();
    body.append('image', blob, filename);
    return firstValueFrom(
      this.http.post<ImageAnalysisResponse>(`${environment.apiUrl}/reports/analyse-image`, body),
    );
  }

  async downloadPdf(report: TechnicalReport): Promise<void> {
    const filename = `${report.claimReference}.pdf`;
    const pdf = await firstValueFrom(
      this.http.post(
        `${environment.apiUrl}/reports/generate-pdf`,
        { report, filename },
        { responseType: 'blob' },
      ),
    );
    const url = URL.createObjectURL(pdf);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  private asDataUrl(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });
  }
}
