export type UserRole =
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
  floor: number | null;
  is_available: boolean;
}

export interface Message {
  message: string;
}

export const roleLabels: Record<UserRole, string> = {
  housekeeping_manager: "Housekeeping Manager",
  housekeeping_staff: "Housekeeping Staff",
  receptionist: "Receptionist",
};

export const dashboardPaths: Record<UserRole, string> = {
  housekeeping_manager: "/manager",
  housekeeping_staff: "/staff",
  receptionist: "/reception",
};

export type ServiceType =
  | "cleaning"
  | "towels"
  | "toiletries"
  | "water"
  | "pillows"
  | "issue"
  | "other";

export type TaskStatus =
  | "submitted"
  | "pending_assignment"
  | "offered"
  | "accepted"
  | "in_progress"
  | "completed"
  | "escalated"
  | "cancelled";

export type TaskPriority = "low" | "normal" | "high" | "urgent";

export type RoomStatus =
  | "cleaning_required"
  | "cleaning_in_progress"
  | "awaiting_inspection"
  | "ready";

export interface Task {
  id: number;
  reference: string;
  room_number: string;
  floor: number;
  service: ServiceType;
  priority: TaskPriority;
  status: TaskStatus;
  instructions: string;
  created_at: string;
  due_at: string;
  overdue: boolean;
  accepted_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  source?: "guest" | "reception";
  assigned_to?: string | null;
  attempts?: number;
  alert_reason?: string | null;
  estimated_completion_at?: string | null;
}

export interface TaskOffer {
  offer_id: number;
  expires_at: string;
  task: Task;
}

export interface TaskEventEntry {
  event: string;
  detail: string;
  actor: string | null;
  created_at: string;
}

export interface StaffMember {
  id: number;
  email: string;
  floor: number | null;
  is_available: boolean;
  workload: number;
}

export interface AssignmentSettings {
  adjacent_floor_range: number;
  max_offer_attempts: number;
  offer_timeout_seconds: number;
  max_active_tasks_per_staff: number;
  priority_rules?: string[];
}

export interface OfferOutcome {
  id: number;
  task_id: number;
  reference: string;
  room_number: string;
  service: ServiceType;
  staff: string;
  outcome: "declined" | "expired";
  responded_at: string | null;
  task_status: TaskStatus;
}

export interface Room {
  id: number;
  number: string;
  floor: number;
  status: RoomStatus;
}

export interface RoomOccupancy {
  guest_name: string;
  phone_last4: string;
  check_in_at: string;
  check_out_at: string;
}

export interface RoomWithRequests extends Room {
  occupancy: RoomOccupancy | null;
  available: boolean;
  open_requests: Task[];
}

export type OccupancyFilter = "all" | "available" | "occupied";

export interface OccupancySummary {
  total: number;
  occupied: number;
  available: number;
  needs_cleaning: number;
}

export interface GuestRoom {
  room_number: string;
  services: ServiceType[];
}

export interface GuestRequest {
  id: number;
  reference: string;
  service: ServiceType;
  instructions: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  estimated_completion_at: string | null;
}

export const serviceLabels: Record<ServiceType, string> = {
  cleaning: "Room Cleaning",
  towels: "Fresh Towels",
  toiletries: "Toiletries",
  water: "Drinking Water",
  pillows: "Extra Pillows",
  issue: "Room Issue",
  other: "Other Request",
};

export const taskStatusLabels: Record<TaskStatus, string> = {
  submitted: "Submitted",
  pending_assignment: "Pending assignment",
  offered: "Offered",
  accepted: "Accepted",
  in_progress: "In progress",
  completed: "Completed",
  escalated: "Escalated",
  cancelled: "Cancelled",
};

export const roomStatusLabels: Record<RoomStatus, string> = {
  cleaning_required: "Cleaning Required",
  cleaning_in_progress: "Cleaning in Progress",
  awaiting_inspection: "Awaiting Inspection",
  ready: "Ready",
};

export const priorityLabels: Record<TaskPriority, string> = {
  low: "Low",
  normal: "Normal",
  high: "High",
  urgent: "Urgent",
};
