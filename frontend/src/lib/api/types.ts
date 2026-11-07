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
