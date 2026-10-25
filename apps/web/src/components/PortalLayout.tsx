import { useState, type ReactNode } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../state/AuthContext";
import { dashboardPaths, roleLabels, type UserRole } from "../types";

export function PortalLayout({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
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
      <section className={wide ? "portal-content portal-content-wide" : "portal-content"}>
        {children}
      </section>
    </main>
  );
}

/**
 * Renders a dashboard only for the role it belongs to. Other signed-in users are
 * sent to their own dashboard. The API enforces the same rules independently.
 */
export function RoleRoute({ role, children }: { role: UserRole; children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading your account…</div>;
  if (!user || !user.role) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to={dashboardPaths[user.role]} replace />;
  return children;
}
