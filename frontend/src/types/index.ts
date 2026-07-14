export type Role = 'ADMIN' | 'TEACHER' | 'AUDITOR'
export interface UserInfo { id: number; username: string; displayName: string; role: Role }
export interface ApiResponse<T> { code: number; message: string; data: T }
export interface PageQuery { current: number; size: number; keyword?: string; status?: string; [key: string]: unknown }
export interface PageResult<T> { records: T[]; total: number; current: number; size: number }
export interface Project { id: number; name: string; teacher: string; startDate: string; endDate: string; status: string }
export interface Student { student_id: number; student_no: string; student_name: string; college: string; major: string; class_name: string; phone?: string }
export interface Template { template_id: number; name: string; issuer: string; course_name: string; project_name: string; certificate_title: string; content: string; issue_year: string; fields: string[]; enabled: boolean; updated_at: string }
export interface Batch { batch_id: number; batch_no: string; batch_name: string; project_name: string; template_id: number; student_count: number; generated: number; evidenced: number; status: string }
export interface Certificate { certificate_id: number; certificate_no: string; student_id: number; student_no: string; student_name: string; batch_id: number; template_id: number; pdf_path: string; certificate_hash: string; qr_code_path: string; verify_url: string; receipt_id: string; status: string; credential_type: 'CERTIFICATE' | string; root_id?: string; project_name: string; issue_date: string; evidence_status: string; previous_certificate_no?: string; new_certificate_no?: string }
export interface ChainRecord { receipt_id: string; certificate_id?: number; certificate_no: string; certificate_hash: string; evidence_type: string; previous_hash?: string; current_block_hash?: string; block_height: number; tx_hash?: string; contract_address?: string; evidence_time: string; status: string }
export interface AuditLog { id: number; operator: string; action: string; module: string; target: string; detail?: string; result: string; createdAt: string }
export interface DashboardStatistics { projectCount: number; student_count: number; certificateCount: number; evidencedCount: number; validCount: number; revokedCount: number; recentReceipts: ChainRecord[]; recentLogs: AuditLog[] }
export interface IssueRequest { project_id: number; template_id: number; batch_id: number; student_ids: number[]; issue_date: string }
export interface IssueResult { success_count: number; failed_count: number; failures: Array<{ student_id?: number; student_name?: string; reason: string }> }
export interface ImportResult { success_count: number; failed_count: number; failures: Array<{ row: number; reason: string }> }