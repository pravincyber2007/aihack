import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import {
  priorityLabels,
  roomStatusLabels,
  serviceLabels,
  taskStatusLabels,
  type RoomStatus,
  type Task,
  type TaskPriority,
  type TaskStatus,
} from "../types";

export const REFRESH_MS = 10_000;

/** Loads data immediately and then every `intervalMs`, keeping the last good result. */
export function usePolling<T>(load: () => Promise<T>, intervalMs = REFRESH_MS) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const loadRef = useRef(load);
  loadRef.current = load;

  const refresh = useCallback(async () => {
    try {
      setData(await loadRef.current());
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), intervalMs);
    return () => window.clearInterval(timer);
  }, [refresh, intervalMs]);

  return { data, error, loading, refresh };
}

/** Runs an action, tracking which item is busy and surfacing errors. */
export function useAction() {
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const run = useCallback(async (key: string, action: () => Promise<unknown>, message = "") => {
    setBusyKey(key);
    setError("");
    setSuccess("");
    try {
      await action();
      setSuccess(message);
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Something went wrong");
      return false;
    } finally {
      setBusyKey(null);
    }
  }, []);

  return { busyKey, error, success, run, setError, setSuccess };
}

export function formatTime(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  const sameDay = date.toDateString() === new Date().toDateString();
  return sameDay
    ? date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function timeUntil(value: string) {
  const seconds = Math.round((new Date(value).getTime() - Date.now()) / 1000);
  if (seconds <= 0) return "expiring";
  if (seconds < 60) return `${seconds}s left`;
  return `${Math.ceil(seconds / 60)} min left`;
}

export function Badge({ tone, children }: { tone: string; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

const statusTones: Record<TaskStatus, string> = {
  submitted: "neutral",
  pending_assignment: "warning",
  offered: "info",
  accepted: "info",
  in_progress: "progress",
  completed: "success",
  escalated: "danger",
  cancelled: "neutral",
};

export function TaskStatusBadge({ status }: { status: TaskStatus }) {
  return <Badge tone={statusTones[status]}>{taskStatusLabels[status]}</Badge>;
}

const priorityTones: Record<TaskPriority, string> = {
  low: "neutral",
  normal: "info",
  high: "warning",
  urgent: "danger",
};

export function PriorityBadge({ priority }: { priority: TaskPriority }) {
  return <Badge tone={priorityTones[priority]}>{priorityLabels[priority]}</Badge>;
}

const roomTones: Record<RoomStatus, string> = {
  cleaning_required: "warning",
  cleaning_in_progress: "progress",
  awaiting_inspection: "info",
  ready: "success",
};

export function RoomStatusBadge({ status }: { status: RoomStatus }) {
  return <Badge tone={roomTones[status]}>{roomStatusLabels[status]}</Badge>;
}

export function Panel({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h3>{title}</h3>
          {description && <p className="panel-description">{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

export function StatGrid({ stats }: { stats: Array<{ label: string; value: number | string; tone?: string }> }) {
  return (
    <div className="stat-grid">
      {stats.map((stat) => (
        <div className={`stat stat-${stat.tone ?? "neutral"}`} key={stat.label}>
          <span>{stat.label}</span>
          <strong>{stat.value}</strong>
        </div>
      ))}
    </div>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return <div className="state-box" role="status">{label}</div>;
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="state-box">{children}</div>;
}

export function Notice({ error, success }: { error?: string; success?: string }) {
  if (error) return <p className="feedback error" role="alert">{error}</p>;
  if (success) return <p className="feedback success" role="status">{success}</p>;
  return null;
}

export function LiveIndicator() {
  return <span className="live-indicator">Live · refreshes every {REFRESH_MS / 1000}s</span>;
}

/** Compact, responsive task list used by the admin, manager, and reception views. */
export function TaskTable({
  tasks,
  showAssignee = false,
  showEta = false,
  renderActions,
}: {
  tasks: Task[];
  showAssignee?: boolean;
  showEta?: boolean;
  renderActions?: (task: Task) => ReactNode;
}) {
  return (
    <div className="task-table" role="table">
      <div className="task-row task-row-head" role="row">
        <span role="columnheader">Request</span>
        <span role="columnheader">Room</span>
        <span role="columnheader">Priority</span>
        <span role="columnheader">Status</span>
        <span role="columnheader">{showAssignee ? "Assigned to" : showEta ? "Estimate" : "Due"}</span>
        {renderActions && <span role="columnheader">Actions</span>}
      </div>
      {tasks.map((task) => (
        <div className="task-row" role="row" key={task.id}>
          <span role="cell" className="task-main">
            <strong>{serviceLabels[task.service]}</strong>
            <small>{task.reference} · {formatTime(task.created_at)}{task.source ? ` · ${task.source}` : ""}</small>
            {task.alert_reason && <small className="alert-text">{task.alert_reason}</small>}
          </span>
          <span role="cell" data-label="Room">{task.room_number} <small>· floor {task.floor}</small></span>
          <span role="cell" data-label="Priority"><PriorityBadge priority={task.priority} /></span>
          <span role="cell" data-label="Status">
            <TaskStatusBadge status={task.status} />
            {task.overdue && <Badge tone="danger">Overdue</Badge>}
          </span>
          <span role="cell" data-label={showAssignee ? "Assigned to" : showEta ? "Estimate" : "Due"}>
            {showAssignee
              ? task.assigned_to ?? "—"
              : showEta
                ? task.status === "completed"
                  ? `Done ${formatTime(task.completed_at)}`
                  : task.estimated_completion_at
                    ? `~${formatTime(task.estimated_completion_at)}`
                    : "Not enough data"
                : formatTime(task.due_at)}
          </span>
          {renderActions && <span role="cell" className="task-actions">{renderActions(task)}</span>}
        </div>
      ))}
    </div>
  );
}
