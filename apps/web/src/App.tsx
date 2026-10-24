import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  Link,
  Navigate,
  Route,
  Routes,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { api } from "./api/client";
import { useAuth } from "./state/AuthContext";
import { roleLabels, type UserRole } from "./types";

const roles: UserRole[] = [
  "administrator",
  "receptionist",
  "housekeeping_manager",
  "housekeeping_staff",
];

function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="auth-shell">
      <section className="brand-panel">
        <div className="brand-illustration" aria-hidden="true">
          <svg viewBox="0 0 720 520">
            <defs>
              <linearGradient id="lobby-wall" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stopColor="#f7f5ef" />
                <stop offset="1" stopColor="#e9e8dc" />
              </linearGradient>
              <linearGradient id="lobby-floor" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stopColor="#e3e1d6" />
                <stop offset="1" stopColor="#cfd3c5" />
              </linearGradient>
              <linearGradient id="reception-desk" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stopColor="#66836d" />
                <stop offset="1" stopColor="#3e5d4d" />
              </linearGradient>
              <linearGradient id="window-glass" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stopColor="#dce7de" />
                <stop offset="1" stopColor="#bacdc0" />
              </linearGradient>
            </defs>
            <path d="M61 378V107q0-13 13-13h572q13 0 13 13v271z" fill="url(#lobby-wall)" />
            <path d="M61 378h598v23H61z" fill="#d1d3c7" />
            <path d="M61 401h598l48 75H13z" fill="url(#lobby-floor)" />
            <path d="M110 134h174v188H110z" fill="#fff" />
            <path d="M121 145h152v165H121z" fill="url(#window-glass)" />
            <path d="M197 145v165m-76-79h152" stroke="#f8f7f1" strokeWidth="8" />
            <path d="M119 309h156" stroke="#a5baa9" strokeWidth="2" />
            <path d="M479 94v211q0 51 51 51t51-51V94" fill="#d8ddd1" />
            <path d="M493 94v211q0 37 37 37t37-37V94" fill="#bccdbf" />
            <path d="M508 94v205q0 23 22 23t22-23V94" fill="#e8e9df" />
            <path d="M335 156h17v76h-17m17-75h28v75h-28m-17-1h45" fill="none" stroke="#718a74" strokeWidth="3" />
            <path d="M343 169h30m-30 11h30m-30 11h20" stroke="#a5b5a2" strokeWidth="2" />
            <path d="M308 303h241v90H308z" fill="url(#reception-desk)" />
            <path d="M293 288h272v25H293z" fill="#788e76" />
            <path d="M327 322h203" stroke="#849984" strokeWidth="2" opacity=".7" />
            <path d="M346 347h161" stroke="#789078" strokeWidth="2" opacity=".7" />
            <path d="M370 366h113v27H370z" fill="#ecebe2" />
            <path d="M349 390h155v7H349z" fill="#b7c3af" />
            <path d="M87 401h566" stroke="#fff" strokeWidth="2" opacity=".8" />
            <path d="m117 402-19 74m108-74-8 74m274-74 8 74m107-74 20 74" stroke="#c0c6b9" strokeWidth="2" opacity=".7" />
            <ellipse cx="359" cy="463" rx="254" ry="12" fill="#aeb8a9" opacity=".28" />
            <path d="M370 94V54m0 0q0-14 13-14t13 14v40" fill="none" stroke="#b3aa91" strokeWidth="2" />
            <path d="M363 94h40l-5 13h-30z" fill="#d7c99e" />
            <path d="M421 94V68m0 0q0-11 10-11t10 11v26" fill="none" stroke="#b3aa91" strokeWidth="2" />
            <path d="M415 94h32l-4 11h-24z" fill="#d7c99e" />
            <path d="M82 376q-3-66 26-87 31 21 27 87z" fill="#6d846b" />
            <path d="M99 330q-30-30-31-55 32 5 45 35m-12-5q23-34 49-35-7 29-41 49" fill="none" stroke="#758d70" strokeWidth="8" strokeLinecap="round" />
            <path d="M77 378h66v13H77z" fill="#b3a68f" />
            <path d="M607 381q-2-46 20-61 23 16 20 61z" fill="#788c70" />
            <path d="M621 350q-21-21-22-40 23 4 32 26m-8-4q17-25 36-26-5 21-30 36" fill="none" stroke="#83947a" strokeWidth="6" strokeLinecap="round" />
            <path d="M601 383h53v11h-53z" fill="#b3a68f" />
            <path d="M76 108h572" stroke="#fff" strokeWidth="2" opacity=".8" />
          </svg>
        </div>
        <div className="brand-copy">
          <h1>Every stay starts with a team that cares.</h1>
          <p className="brand-description">
            A calm, connected place for the people who make every guest feel at home.
          </p>
        </div>
        <div className="brand-footer">A better day, one thoughtful detail at a time.</div>
      </section>
      <section className="form-panel">
        <div className="form-wrap">{children}</div>
      </section>
    </main>
  );
}

function Field({
  label,
  type = "text",
  value,
  onChange,
  autoComplete,
  required = true,
  minLength,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete?: string;
  required?: boolean;
  minLength?: number;
}) {
  const id = useId();
  const [passwordVisible, setPasswordVisible] = useState(false);
  const isPassword = type === "password";

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className="field-input-wrap">
        <input
          id={id}
          type={isPassword && passwordVisible ? "text" : type}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          autoComplete={autoComplete}
          required={required}
          minLength={minLength}
        />
        {isPassword && (
          <button
            className="password-toggle"
            type="button"
            onClick={() => setPasswordVisible((visible) => !visible)}
            aria-label={passwordVisible ? "Hide password" : "Show password"}
            aria-pressed={passwordVisible}
          >
            {passwordVisible ? (
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M3 3l18 18M10.6 10.6a2 2 0 002.8 2.8" />
                <path d="M9.9 5.2A10.8 10.8 0 0112 5c5.2 0 8.8 4.5 10 7a13.4 13.4 0 01-3.2 4.1M6.2 6.2A14 14 0 002 12c1.2 2.5 4.8 7 10 7 1 0 2-.2 2.9-.5" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            )}
          </button>
        )}
      </div>
    </div>
  );
}

function FormFeedback({ error, success }: { error: string; success: string }) {
  if (error) return <p className="feedback error" role="alert">{error}</p>;
  if (success) return <p className="feedback success" role="status">{success}</p>;
  return null;
}

function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [selectedRole, setSelectedRole] = useState<UserRole | "">("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const { signIn } = useAuth();
  const navigate = useNavigate();

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (!selectedRole) {
        setError("Choose your assigned role to continue.");
        return;
      }
      const user = await api.login(email, password, selectedRole);
      signIn(user);
      navigate(user.role === "administrator" ? "/admin" : "/dashboard");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  async function resendVerification() {
    setError("");
    try {
      const result = await api.resendVerification(email);
      setSuccess(result.message);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not resend the link");
    }
  }

  return (
    <AuthLayout>
      <p className="eyebrow">Welcome back</p>
      <h2>Sign in to your account</h2>
      <p className="muted">Use your work email to continue to the staff portal.</p>
      <form className="form" onSubmit={submit}>
        <Field label="Work email" type="email" value={email} onChange={setEmail} autoComplete="email" />
        <label className="field">
          <span>Your role</span>
          <select
            className="role-select"
            value={selectedRole}
            onChange={(event) => setSelectedRole(event.target.value as UserRole | "")}
            required
          >
            <option value="" disabled>Select your assigned role</option>
            {roles.map((role) => (
              <option value={role} key={role}>{roleLabels[role]}</option>
            ))}
          </select>
          <span className="field-hint">Your role must match the one assigned by your administrator.</span>
        </label>
        <Field label="Password" type="password" value={password} onChange={setPassword} autoComplete="current-password" />
        <div className="form-row forgot-row">
          <Link to="/forgot-password">Forgot password?</Link>
        </div>
        <FormFeedback error={error} success={success} />
        {error.toLowerCase().includes("verify your email") && (
          <button className="text-button" type="button" onClick={resendVerification}>
            Resend verification email
          </button>
        )}
        <button className="primary-button" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p className="form-switch">
        New to the team? <Link to="/register">Create an account</Link>
      </p>
    </AuthLayout>
  );
}

function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (password !== confirmation) {
      setError("Your passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      const result = await api.register(email, password);
      setSuccess(result.message);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <p className="eyebrow">Join the team</p>
      <h2>Create your account</h2>
      <p className="muted">An administrator will assign your role after you verify your email.</p>
      <form className="form" onSubmit={submit}>
        <Field label="Work email" type="email" value={email} onChange={setEmail} autoComplete="email" />
        <Field label="Password" type="password" value={password} onChange={setPassword} autoComplete="new-password" minLength={12} />
        <p className="field-hint">Use at least 12 characters.</p>
        <Field label="Confirm password" type="password" value={confirmation} onChange={setConfirmation} autoComplete="new-password" />
        <FormFeedback error={error} success={success} />
        <button className="primary-button" disabled={busy}>
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>
      <p className="form-switch">
        Already registered? <Link to="/login">Sign in</Link>
      </p>
    </AuthLayout>
  );
}

function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api.forgotPassword(email);
      setSuccess(result.message);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not request a reset");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <p className="eyebrow">Account recovery</p>
      <h2>Reset your password</h2>
      <p className="muted">Enter your work email and we’ll send a secure reset link.</p>
      <form className="form" onSubmit={submit}>
        <Field label="Work email" type="email" value={email} onChange={setEmail} autoComplete="email" />
        <FormFeedback error={error} success={success} />
        <button className="primary-button" disabled={busy}>
          {busy ? "Sending…" : "Send reset link"}
        </button>
      </form>
      <p className="form-switch"><Link to="/login">Back to sign in</Link></p>
    </AuthLayout>
  );
}

function ResetPasswordPage() {
  const [params] = useSearchParams();
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const token = params.get("token") ?? "";

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (password !== confirmation) {
      setError("Your passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      const result = await api.resetPassword(token, password);
      setSuccess(result.message);
      window.setTimeout(() => navigate("/login"), 1200);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not reset your password");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <p className="eyebrow">Account recovery</p>
      <h2>Choose a new password</h2>
      {!token && <p className="feedback error">This reset link is missing or invalid.</p>}
      {token && (
        <form className="form" onSubmit={submit}>
          <Field label="New password" type="password" value={password} onChange={setPassword} autoComplete="new-password" minLength={12} />
          <p className="field-hint">Use at least 12 characters.</p>
          <Field label="Confirm password" type="password" value={confirmation} onChange={setConfirmation} autoComplete="new-password" />
          <FormFeedback error={error} success={success} />
          <button className="primary-button" disabled={busy}>
            {busy ? "Updating…" : "Update password"}
          </button>
        </form>
      )}
      <p className="form-switch"><Link to="/login">Back to sign in</Link></p>
    </AuthLayout>
  );
}

function VerifyEmailPage() {
  const [params] = useSearchParams();
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const token = params.get("token") ?? "";
  const requestStarted = useRef(false);

  useEffect(() => {
    if (requestStarted.current) return;
    requestStarted.current = true;
    if (!token) {
      setError("This verification link is missing or invalid.");
      return;
    }
    api
      .verifyEmail(token)
      .then((result) => setSuccess(result.message))
      .catch((cause: unknown) =>
        setError(cause instanceof Error ? cause.message : "Email verification failed"),
      );
  }, [token]);

  return (
    <AuthLayout>
      <p className="eyebrow">Email verification</p>
      <h2>Verify your email</h2>
      <FormFeedback error={error} success={success} />
      {success && <p className="form-switch"><Link to="/login">Continue to sign in</Link></p>}
    </AuthLayout>
  );
}

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading your account…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function PortalLayout({ children }: { children: ReactNode }) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [logoutError, setLogoutError] = useState("");

  async function logout() {
    try {
      await signOut();
      setLogoutError("");
      navigate("/login");
    } catch (cause) {
      setLogoutError(
        cause instanceof Error ? cause.message : "Could not securely sign out",
      );
    }
  }

  return (
    <main className="portal-shell">
      <header className="portal-header">
        <Link className="brand" to="/">
          <span className="brand-mark">S</span>
          <span>staff<span className="brand-light"> / portal</span></span>
        </Link>
        <div className="profile">
          <div>
            <strong>{user?.email}</strong>
            <span>{user?.role ? roleLabels[user.role] : "Staff"}</span>
          </div>
          <button className="quiet-button" onClick={logout}>Sign out</button>
        </div>
      </header>
      {logoutError && (
        <p className="feedback error logout-error" role="alert">{logoutError}</p>
      )}
      <section className="portal-content">{children}</section>
    </main>
  );
}

function DashboardPage() {
  const { user } = useAuth();
  return (
    <PortalLayout>
      <p className="eyebrow">Staff portal</p>
      <h1>Good to have you here.</h1>
      <p className="muted">
        You’re signed in as {user?.role ? roleLabels[user.role].toLowerCase() : "a team member"}.
        Your workspace is ready for the next step.
      </p>
      <div className="welcome-card">
        <span className="welcome-icon">✦</span>
        <div><strong>Your team, in one place</strong><p>Staff tools and hotel workflows can be added here.</p></div>
      </div>
    </PortalLayout>
  );
}

function AdminPage() {
  const [users, setUsers] = useState<Awaited<ReturnType<typeof api.pendingUsers>>>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function loadUsers() {
    setError("");
    try {
      setUsers(await api.pendingUsers());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load pending accounts");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadUsers();
  }, []);

  async function assign(userId: number, role: UserRole) {
    setBusyId(userId);
    setError("");
    try {
      await api.assignRole(userId, role);
      setUsers((current) => current.filter((user) => user.id !== userId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not assign role");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Protected>
      <PortalLayout>
        <p className="eyebrow">Administration</p>
        <h1>Review staff accounts</h1>
        <p className="muted">Only verified accounts appear here. Assign the right role to activate access.</p>
        <FormFeedback error={error} success="" />
        {loading ? (
          <div className="empty-state">Loading pending accounts…</div>
        ) : users.length === 0 ? (
          <div className="empty-state">No verified accounts are waiting for approval.</div>
        ) : (
          <div className="user-list">
            {users.map((user) => (
              <article className="user-row" key={user.id}>
                <div className="user-avatar">{user.email.slice(0, 1).toUpperCase()}</div>
                <div className="user-details">
                  <strong>{user.email}</strong>
                  <span>Email verified · waiting for approval</span>
                </div>
                <label className="role-control">
                  <span className="sr-only">Role for {user.email}</span>
                  <select
                    defaultValue=""
                    disabled={busyId === user.id}
                    onChange={(event) => {
                      if (event.target.value) void assign(user.id, event.target.value as UserRole);
                    }}
                  >
                    <option value="" disabled>Assign role…</option>
                    {roles.map((role) => (
                      <option value={role} key={role}>{roleLabels[role]}</option>
                    ))}
                  </select>
                </label>
              </article>
            ))}
          </div>
        )}
      </PortalLayout>
    </Protected>
  );
}

function AdminRoute() {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading your account…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "administrator") return <Navigate to="/dashboard" replace />;
  return <AdminPage />;
}

function HomeRoute() {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading your account…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === "administrator" ? "/admin" : "/dashboard"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeRoute />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route path="/dashboard" element={<Protected><DashboardPage /></Protected>} />
      <Route path="/admin" element={<AdminRoute />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
