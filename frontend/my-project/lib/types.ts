export type Role = "owner" | "barber";
export interface StaffUser { id:number; username:string; email:string; display_name:string; role:Role; barber_id?:number|null; branch_id?:number|null; must_change_password?:boolean; }
export interface AuthResult { access_token:string; token_type:string; expires_in:number; user:StaffUser; }
export interface Branch { id:number; name:string; location?:string; address?:string; }
export interface Barber { id:number; name:string; branch_id:number; is_active?:boolean; }
export interface ServiceCatalogItem { name:string; default_price:number; }
export interface Customer { id:number; name:string; phone?:string; location?:string; visit_count:number; last_visit?:string|null; }
export interface ServiceLine { id?:number; service_name:string; quantity:number; unit_price:number; line_total:number; }
export interface Visit { id:number; customer_id:number; customer_name:string; customer_phone?:string; customer_location?:string; branch_id:number; branch_name:string; barber_id:number; barber_name:string; service_name:string; amount:number; completed_at:string; service_items?:ServiceLine[]; feedback_received?:boolean; feedback_requested?:boolean; rating?:number|null; feedback_comment?:string|null; feedback_created_at?:string|null; customer_rating?:number|null; customer_rating_note?:string; visit_number?:number; visit_count?:number; is_latest_visit?:boolean; can_edit?:boolean; }
export interface Feedback { id:number; visit_id:number; customer_name:string; branch_name:string; barber_name:string; rating:number; comment?:string; created_at:string; recovery_task_id?:number|null; }
export interface Review { id:number; visit_id:number; visit_number:number; completed_at:string; created_at:string; service_name:string; amount:number; branch_name:string; barber_name:string; rating:number; comment:string; }
export interface AuditLog { id:number; actor_username:string; actor_role:string; action:string; entity_type:string; entity_id:number; before_data?:Record<string,unknown>|null; after_data?:Record<string,unknown>|null; change_note?:string; created_at:string; }
export interface Notification { id:string; title:string; message:string; customer_id:number; customer_name:string; visit_id:number; visit_number:number; rating:number; service_name:string; amount:number; branch_name:string; barber_name:string; created_at:string; completed_at:string; }
export interface DashboardSummary { total_visits:number; revenue:number; average_rating?:number|null; feedback_count:number; open_recovery_tasks:number; repeat_customer_rate?:number; }
export interface BranchInsight { branch_id?:number; branch_name:string; revenue:number; visits:number; average_rating?:number|null; low_rating_count?:number; }
export interface BarberInsight { barber_id?:number; barber_name:string; branch_name:string; revenue:number; visits:number; feedback_count:number; average_rating?:number|null; }
export interface BootstrapData { user:StaffUser; dashboard:DashboardSummary; branches:Branch[]; barbers:Barber[]; customers:Customer[]; visits:Visit[]; feedback:Feedback[]; tasks:Array<Record<string,unknown>>; insights:{branches:BranchInsight[];barbers:BarberInsight[]}; messages:Array<Record<string,unknown>>; serviceCatalog:ServiceCatalogItem[]; auditLogs:AuditLog[]; }
export interface VisitHistoryEntry { id:number; actor_username:string; actor_role:string; action:string; before_data?:Record<string,unknown>|null; after_data?:Record<string,unknown>|null; change_note?:string; created_at:string; }
