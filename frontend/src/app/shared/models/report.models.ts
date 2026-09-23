export type ReportStatus =
  'Draft' | 'Ready to Submit' | 'Submitted' | 'Email Sent' | 'Email Failed';
export const PHOTO_CATEGORIES = [
  { key: 'dot', label: 'DOT', hint: 'Clear photo of the DOT code', required: true },
  {
    key: 'serialNumber',
    label: 'Serial number',
    hint: 'Clear photo of the serial number',
    required: true,
  },
  {
    key: 'entireTyreDot',
    label: 'Entire tyre (side with DOT)',
    hint: 'Full tyre, DOT side',
    required: true,
  },
  {
    key: 'entireTyreOpposite',
    label: 'Entire tyre (opposite side)',
    hint: 'Full tyre, opposite side',
    required: true,
  },
  {
    key: 'issue1',
    label: 'Issue 1',
    hint: 'Area of concern',
    required: true,
  },
  { key: 'issue2', label: 'Issue 2', hint: 'Another view of the issue', required: false },
  { key: 'bead1', label: 'Bead', hint: 'Close-up of bead area', required: true },
  {
    key: 'internalCarcass1',
    label: 'Internal carcass',
    hint: 'Internal view',
    required: true,
  },
  {
    key: 'treadDepth1',
    label: 'Tread depth (3 photos)',
    hint: 'Left, centre, right',
    required: true,
  },
  {
    key: 'treadPattern',
    label: 'Tread pattern',
    hint: 'Clear tread pattern',
    required: true,
  },
  {
    key: 'vehicle',
    label: 'Vehicle',
    hint: 'Vehicle in view',
    required: true,
  },
] as const;
export interface ReportPhoto {
  category: string;
  name: string;
  label: string;
  previewUrl: string;
  capturedAt: string;
  mimeType: string;
  byteSize: number;
  sha256: string;
  storageId?: string;
}
export interface ReportRecipient {
  id: string;
  company: string;
  contact_name: string;
  email: string;
  default_cc: string;
  is_active: boolean;
  branch_code: string;
  category: string;
  escalation_hours: number;
}
export interface DeliveryAttempt {
  id: string;
  claim_reference: string;
  recipient_email: string;
  cc: string[];
  status: 'Pending' | 'Processing' | 'Retrying' | 'Sent' | 'Failed';
  attempt_count: number;
  message_id: string | null;
  error_message: string | null;
  created_at: string;
  last_attempt_at: string;
  next_attempt_at: string;
}
export interface TechnicalReport {
  id: string;
  claimReference: string;
  createdAt: string;
  updatedAt: string;
  status: ReportStatus;
  branch: string;
  internalExternal: 'Internal' | 'External';
  salesperson: string;
  customerName: string;
  customerInvoiceNumber: string;
  category: string;
  inspectedLocation: string;
  returnedWithRim: boolean | null;
  fittedLoose: 'Fitted' | 'Loose' | '';
  brand: string;
  rimSize: string;
  pattern: string;
  dot: string;
  serialNumber: string;
  claimCode: string;
  remainingTreadDepth: string;
  inspectedPressure: string;
  tyreMileage: string;
  tyrePosition: string;
  natureOfRepair: string;
  vehicleMakeModel: string;
  vehicleMileage: string;
  goodsTransported: string;
  notes: string;
  photos: ReportPhoto[];
}
