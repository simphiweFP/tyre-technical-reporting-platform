export type UserRole = 'administrator' | 'report_capturer' | 'viewer' | 'pending';
export interface CurrentUser {
  id: string;
  email: string;
  full_name: string;
  job_title: string | null;
  role: UserRole;
  branch_id: string | null;
}
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  user: CurrentUser;
}
