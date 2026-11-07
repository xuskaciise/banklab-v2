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
