import type {
  AssignmentSettings,
  GuestRequest,
  GuestRoom,
  Message,
  OccupancyFilter,
  OccupancySummary,
  OfferOutcome,
  Room,
  RoomStatus,
  RoomWithRequests,
  ServiceType,
  StaffMember,
  Task,
  TaskEventEntry,
  TaskOffer,
  TaskStatus,
  User,
  UserRole,
} from "../types";

interface ApiErrorBody {
  detail?: string | Array<{ msg?: string }>;
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const method = options.method ?? "GET";
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");

  if (!["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase())) {
    let csrfResponse: Response;
    try {
      csrfResponse = await fetch("/api/v1/auth/csrf", {
        credentials: "include",
      });
    } catch {
      throw new Error(
        "Could not reach the authentication service. Make sure the backend is running.",
      );
    }
    if (!csrfResponse.ok) {
      throw new Error(
        `Could not start a secure request (HTTP ${csrfResponse.status}).`,
      );
    }
    const csrfBody = (await csrfResponse.json()) as { csrf_token: string };
    headers.set("X-CSRF-Token", csrfBody.csrf_token);
  }

  let response: Response;
  try {
    response = await fetch(path, {
      ...options,
      headers,
      credentials: "include",
    });
  } catch {
    throw new Error(
      "Could not reach the authentication service. Make sure the backend is running.",
    );
  }
  const body = (await response.json().catch(() => ({}))) as
    | T
    | ApiErrorBody;
  if (!response.ok) {
    const error = body as ApiErrorBody;
    const message =
      typeof error.detail === "string"
        ? error.detail
        : error.detail?.map((item) => item.msg).filter(Boolean).join("; ");
    throw new Error(message || "The request could not be completed");
  }
  return body as T;
}

export const api = {
  register(email: string, password: string, role: UserRole) {
    return request<Message>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, role }),
    });
  },
  login(email: string, password: string, selected_role: UserRole) {
    return request<User>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password, selected_role }),
    });
  },
  me() {
    return request<User>("/api/v1/auth/me");
  },
  refresh() {
    return request<User>("/api/v1/auth/refresh", { method: "POST" });
  },
  logout() {
    return request<Message>("/api/v1/auth/logout", { method: "POST" });
  },
  forgotPassword(email: string) {
    return request<Message>("/api/v1/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },
  resetPassword(token: string, password: string) {
    return request<Message>("/api/v1/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    });
  },
};

function send<T>(path: string, body?: unknown, method = "POST") {
  return request<T>(path, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export const tasksApi = {
  list: (statuses: TaskStatus[] = []) =>
    request<Task[]>(
      `/api/v1/tasks${statuses.length ? "?" + statuses.map((s) => `status=${s}`).join("&") : ""}`,
    ),
  summary: () => request<Record<TaskStatus, number>>("/api/v1/tasks/summary"),
  alerts: () => request<Task[]>("/api/v1/tasks/alerts"),
  history: (id: number) =>
    request<{ reference: string; events: TaskEventEntry[] }>(`/api/v1/tasks/${id}/history`),
};

export const managerApi = {
  staff: () => request<StaffMember[]>("/api/v1/manager/staff"),
  setFloor: (id: number, floor: number | null) =>
    send<{ id: number; floor: number | null }>(`/api/v1/manager/staff/${id}`, { floor }, "PATCH"),
  settings: () => request<AssignmentSettings>("/api/v1/manager/settings"),
  saveSettings: (settings: AssignmentSettings) =>
    send<AssignmentSettings>("/api/v1/manager/settings", settings, "PUT"),
  offers: () => request<OfferOutcome[]>("/api/v1/manager/offers"),
  rooms: () =>
    request<{ summary: Record<RoomStatus, number>; rooms: Room[] }>("/api/v1/manager/rooms"),
  inspect: (roomId: number) => send<Room>(`/api/v1/manager/rooms/${roomId}/inspect`),
  retry: (taskId: number) => send<Message>(`/api/v1/manager/tasks/${taskId}/retry`),
  assign: (taskId: number, staffId: number) =>
    send<Message>(`/api/v1/manager/tasks/${taskId}/assign`, { staff_id: staffId }),
  cancel: (taskId: number) => send<Message>(`/api/v1/manager/tasks/${taskId}/cancel`),
};

export const staffApi = {
  me: () => request<{ floor: number | null; is_available: boolean }>("/api/v1/staff/me"),
  setAvailability: (isAvailable: boolean) =>
    send<{ floor: number | null; is_available: boolean }>(
      "/api/v1/staff/me",
      { is_available: isAvailable },
      "PATCH",
    ),
  offers: () => request<TaskOffer[]>("/api/v1/staff/offers"),
  accept: (offerId: number) => send<Task>(`/api/v1/staff/offers/${offerId}/accept`),
  decline: (offerId: number) => send<Message>(`/api/v1/staff/offers/${offerId}/decline`),
  tasks: () => request<Task[]>("/api/v1/staff/tasks"),
  start: (taskId: number) => send<Task>(`/api/v1/staff/tasks/${taskId}/start`),
  complete: (taskId: number) => send<Task>(`/api/v1/staff/tasks/${taskId}/complete`),
};

export const receptionApi = {
  rooms: (query: string, occupancy: OccupancyFilter = "all") =>
    request<RoomWithRequests[]>(
      `/api/v1/reception/rooms?query=${encodeURIComponent(query)}&occupancy=${occupancy}`,
    ),
  summary: () => request<OccupancySummary>("/api/v1/reception/summary"),
  checkIn: (body: { room_number: string; guest_name: string; phone: string; nights: number }) =>
    send<RoomWithRequests>("/api/v1/reception/check-in", body),
  checkOut: (roomNumber: string) =>
    send<RoomWithRequests>("/api/v1/reception/check-out", { room_number: roomNumber }),
  requests: () => request<Task[]>("/api/v1/reception/requests"),
  submit: (body: {
    room_number: string;
    service: ServiceType;
    instructions: string;
    urgent: boolean;
  }) => send<Task>("/api/v1/reception/requests", body),
};

export const guestApi = {
  access: (phone: string) => send<GuestRoom>("/api/v1/guest/access", { phone }),
  me: () => request<GuestRoom>("/api/v1/guest/me"),
  logout: () => send<Message>("/api/v1/guest/logout"),
  requests: () => request<GuestRequest[]>("/api/v1/guest/requests"),
  submit: (body: { service: ServiceType; instructions: string; client_request_id: string }) =>
    send<GuestRequest>("/api/v1/guest/requests", body),
};
