import type { Message, User, UserRole } from "../types";

interface ApiErrorBody {
  detail?: string | Array<{ msg?: string }>;
}

async function request<T>(
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
  register(email: string, password: string) {
    return request<Message>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
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
  verifyEmail(token: string) {
    return request<Message>("/api/v1/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    });
  },
  resendVerification(email: string) {
    return request<Message>("/api/v1/auth/verification/resend", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
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
  pendingUsers() {
    return request<User[]>("/api/v1/admin/users/pending");
  },
  assignRole(userId: number, role: UserRole) {
    return request<User>(`/api/v1/admin/users/${userId}/role`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    });
  },
};
