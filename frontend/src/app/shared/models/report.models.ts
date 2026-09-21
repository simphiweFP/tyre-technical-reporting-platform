export type ReportStatus =
  'Draft' | 'Ready to Submit' | 'Submitted' | 'Email Sent' | 'Email Failed';
export const PHOTO_CATEGORIES = [
  { key: 'dot', label: 'DOT', hint: 'Fill the frame with the DOT marking', required: true },
  {
    key: 'serialNumber',
    label: 'Serial number',
    hint: 'Capture the complete serial number',
    required: true,
  },
  {
    key: 'entireTyreDot',
    label: 'Entire tyre · DOT side',
    hint: 'Show the complete tyre and DOT sidewall',
    required: true,
  },
  {
    key: 'entireTyreOpposite',
    label: 'Entire tyre · opposite',
    hint: 'Show the opposite sidewall',
    required: true,
  },
  {
    key: 'issue1',
    label: 'Issue 1',
    hint: 'Move close enough to show the primary issue',
    required: true,
  },
  { key: 'issue2', label: 'Issue 2', hint: 'Add a second issue when applicable', required: false },
  { key: 'bead1', label: 'Bead 1', hint: 'Capture the first bead area', required: true },
  { key: 'bead2', label: 'Bead 2', hint: 'Capture the second bead area', required: true },
  {
    key: 'fullView',
    label: 'Full view',
    hint: 'Show the complete inspection setup',
    required: true,
  },
  {
    key: 'internalCarcass1',
    label: 'Internal carcass 1',
    hint: 'Capture the inner casing clearly',
    required: true,
  },
  {
    key: 'internalCarcass2',
    label: 'Internal carcass 2',
    hint: 'Capture the opposite inner casing',
    required: true,
  },
  {
    key: 'treadDepth1',
    label: 'Tread depth 1',
    hint: 'Show the measurement in focus',
    required: true,
  },
  {
    key: 'treadDepth2',
    label: 'Tread depth 2',
    hint: 'Show the second measurement',
    required: true,
  },
  {
    key: 'treadDepth3',
    label: 'Tread depth 3',
    hint: 'Show the third measurement',
    required: true,
  },
  {
    key: 'treadPattern',
    label: 'Tread pattern',
    hint: 'Capture the full tread pattern',
    required: true,
  },
  {
    key: 'vehicle',
    label: 'Vehicle',
    hint: 'Show the vehicle and registration when permitted',
    required: true,
  },
] as const;
export interface ReportPhoto {
  category: string;
  name: string;
  previewUrl: string;
  capturedAt: string;
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
