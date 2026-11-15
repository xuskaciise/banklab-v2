// Aliases over the generated OpenAPI types (run `npm run gen:api` after
// backend API changes). Never hand-write API shapes here.
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Me = Schemas["MeOut"];
export type PlatformRole = Me["platform_role"];
export type StaffLoginRequest = Schemas["StaffLoginIn"];
export type StudentLoginRequest = Schemas["StudentLoginIn"];
export type LoginResponse = Schemas["LoginOut"];
export type ChangePasswordRequest = Schemas["ChangePasswordIn"];
export type HealthResponse = Schemas["HealthOut"];

// Lab 1.3 (classes, sessions, banks, members, permissions)
export type ClassOut = Schemas["ClassOut"];
export type ClassIn = Schemas["ClassIn"];
export type StudentOut = Schemas["StudentOut"];
export type AddStudentIn = Schemas["AddStudentIn"];
export type UpdateStudentIn = Schemas["UpdateStudentIn"];
export type CsvResult = Schemas["CsvResultOut"];
export type CsvRow = Schemas["CsvRowOut"];
export type TemplateOut = Schemas["TemplateOut"];
export type TemplateIn = Schemas["TemplateIn"];
export type SessionOut = Schemas["SessionOut"];
export type SessionIn = Schemas["SessionIn"];
export type SessionUpdateIn = Schemas["SessionUpdateIn"];
export type BankOut = Schemas["BankOut"];
export type BusinessDayOut = Schemas["BusinessDayOut"];
export type MemberOut = Schemas["MemberOut"];
export type AddMembersIn = Schemas["AddMembersIn"];
export type PermissionCell = Schemas["PermissionCellOut"];
export type OverrideIn = Schemas["OverrideIn"];
export type MySession = Schemas["MySessionOut"];
export type SessionMe = Schemas["SessionMeOut"];
export type AuditOut = Schemas["AuditOut"];
export type PagedAudit = Schemas["PagedAuditOut"];

// Banking 1.5 (branches, tills, vault, cash transfers)
export type BranchOut = Schemas["BranchOut"];
export type BranchIn = Schemas["BranchIn"];
export type BranchUpdateIn = Schemas["BranchUpdateIn"];
export type TillOut = Schemas["TillOut"];
export type TillIn = Schemas["TillIn"];
export type VaultOut = Schemas["VaultOut"];
export type CashReconciliation = Schemas["CashReconciliationOut"];
export type CashTransferOut = Schemas["TransferOut"];

// Customers 1.6
export type CustomerOut = Schemas["CustomerOut"];
export type PagedCustomer = Schemas["PagedCustomerOut"];
export type CustomerDetail = Schemas["CustomerDetailOut"];
export type CustomerIn = Schemas["CustomerIn"];
export type CustomerUpdateIn = Schemas["CustomerUpdateIn"];
export type PartyLink = Schemas["PartyLinkOut"];
export type PartyIn = Schemas["PartyIn"];
export type AddPartyIn = Schemas["AddPartyIn"];
export type PartyUpdateIn = Schemas["PartyUpdateIn"];
export type DocumentOut = Schemas["DocumentOut"];
export type DocumentIn = Schemas["DocumentIn"];
export type DocumentUpdateIn = Schemas["DocumentUpdateIn"];
export type KinOut = Schemas["KinOut"];
export type KinIn = Schemas["KinIn"];

// Accounts 1.7
export type ProductOut = Schemas["ProductOut"];
export type AccountOut = Schemas["AccountOut"];
export type PagedAccount = Schemas["PagedAccountOut"];
export type AccountIn = Schemas["AccountIn"];
export type KycItem = Schemas["KycItemOut"];

// Teller session 1.8
export type TillAvailability = Schemas["TillAvailabilityOut"];
export type TellerSession = Schemas["TellerSessionOut"];
export type CashCount = Schemas["CashCountOut"];
export type OpenRequestIn = Schemas["OpenRequestIn"];
export type CloseCountIn = Schemas["CloseCountIn"];
export type DenominationOut = Schemas["DenominationOut"];

// Transactions 1.9
export type TransactionOut = Schemas["TransactionOut"];
export type PagedTransaction = Schemas["PagedTransactionOut"];
export type ApprovalOut = Schemas["ApprovalOut"];
export type DepositIn = Schemas["DepositIn"];
export type WithdrawalIn = Schemas["WithdrawalIn"];
export type ChequeWithdrawalIn = Schemas["ChequeWithdrawalIn"];
export type ChequebookOut = Schemas["ChequebookOut"];
export type ChequeOut = Schemas["ChequeOut"];
export type TransferIn = Schemas["TransferIn"];

// 1.11 End of day
export type EodStatus = Schemas["EodStatusOut"];
export type EodCheck = Schemas["EodCheckOut"];
export type EodClose = Schemas["EodCloseOut"];

// Platform settings (1.12a)
export type PlatformSettings = Schemas["PlatformSettingsOut"];
export type PlatformSettingsIn = Schemas["PlatformSettingsIn"];

// Admin console (1.12b)
export type InstructorOut = Schemas["InstructorOut"];
export type InstructorIn = Schemas["InstructorIn"];
export type AdminStudentOut = Schemas["AdminStudentOut"];
export type InstitutionOut = Schemas["InstitutionOut"];
export type CoaTemplateRow = Schemas["CoaTemplateRow"];
export type CoaTemplateDetail = Schemas["CoaTemplateDetail"];
export type CoaLineOut = Schemas["CoaLineOut"];
export type CoaLineIn = Schemas["CoaLineIn"];
export type CoaLinePatch = Schemas["CoaLinePatch"];
export type SessionTemplateOut = Schemas["SessionTemplateOut"];
export type SessionTemplateIn = Schemas["SessionTemplateIn"];

// Dashboards + Dr/Cr learning panel 1.13
export type SessionDashboard = Schemas["DashboardOut"];
export type TellerDashboard = Schemas["TellerDashboardOut"];
export type ManagerDashboard = Schemas["ManagerDashboardOut"];
export type StaffDashboard = Schemas["StaffDashboardOut"];
export type DashboardSession = Schemas["DashboardSessionOut"];
export type DashboardEvent = Schemas["DashboardEventOut"];
export type Learning = Schemas["LearningOut"];

// Exam sessions (1.14)
export type CheckType = Schemas["CheckTypeOut"];
export type ExamOut = Schemas["ExamOut"];
export type ExamIn = Schemas["ExamIn"];
export type ExamTask = Schemas["TaskOut"];
export type ExamTaskIn = Schemas["TaskIn"];
export type ExamTaskPatch = Schemas["TaskPatch"];
export type ExamResults = Schemas["ResultsOut"];
export type ExamStudentRow = Schemas["StudentRowOut"];
export type ExamTaskResult = Schemas["TaskResultOut"];
export type StudentExam = Schemas["StudentExamOut"];
export type StudentTask = Schemas["StudentTaskOut"];
export type MyExamResult = Schemas["MyResultOut"];
export type ExamClock = Schemas["ExamClockOut"];
