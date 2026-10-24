export type UserRole =
  | "administrator"
  | "receptionist"
  | "housekeeping_manager"
  | "housekeeping_staff";

export type UserStatus = "pending" | "active" | "disabled";

export interface User {
  id: number;
  email: string;
  role: UserRole | null;
  status: UserStatus;
  email_verified: boolean;
}

export interface Message {
  message: string;
}

export const roleLabels: Record<UserRole, string> = {
  administrator: "Administrator",
  receptionist: "Receptionist",
  housekeeping_manager: "Housekeeping manager",
  housekeeping_staff: "Housekeeping staff",
};
