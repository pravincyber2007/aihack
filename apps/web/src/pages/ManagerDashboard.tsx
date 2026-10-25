import { useState, type FormEvent } from "react";
import { managerApi, tasksApi } from "../api/client";
import { PortalLayout } from "../components/PortalLayout";
import { TaskHistory } from "../components/TaskHistory";
import {
  Badge,
  EmptyState,
  formatTime,
  LiveIndicator,
  LoadingState,
  Notice,
  Panel,
  RoomStatusBadge,
  StatGrid,
  TaskTable,
  useAction,
  usePolling,
} from "../components/ui";
import {
  roomStatusLabels,
  serviceLabels,
  type AssignmentSettings,
  type RoomStatus,
  type StaffMember,
  type Task,
} from "../types";

type Tab = "exceptions" | "tasks" | "staff" | "offers" | "rooms" | "settings";
type TaskFilter = "pending" | "urgent" | "accepted" | "in_progress" | "completed" | "all";

const tabLabels: Record<Tab, string> = {
  exceptions: "Alerts",
  tasks: "Tasks",
  staff: "Staff & floors",
  offers: "Declined / timed out",
  rooms: "Room readiness",
  settings: "Assignment rules",
};

const filterLabels: Record<TaskFilter, string> = {
  pending: "Pending",
  urgent: "Urgent",
  accepted: "Accepted",
  in_progress: "In progress",
  completed: "Completed",
  all: "All",
};

function matchesFilter(task: Task, filter: TaskFilter) {
  switch (filter) {
    case "pending":
      return ["submitted", "pending_assignment", "offered", "escalated"].includes(task.status);
    case "urgent":
      return task.priority === "urgent" && !["completed", "cancelled"].includes(task.status);
    case "all":
      return true;
    default:
      return task.status === filter;
  }
}

function ExceptionActions({ task, staff, onDone }: { task: Task; staff: StaffMember[]; onDone: () => void }) {
  const [staffId, setStaffId] = useState("");
  const action = useAction();
  const busy = action.busyKey !== null;
  const run = async (key: string, fn: () => Promise<unknown>) => {
    if (await action.run(key, fn)) onDone();
  };

  return (
    <div className="exception-actions">
      <button className="small-button" disabled={busy} onClick={() => run("retry", () => managerApi.retry(task.id))}>
        Retry auto-assign
      </button>
      <select className="compact-select" value={staffId} onChange={(event) => setStaffId(event.target.value)} aria-label={`Assign ${task.reference} to`}>
        <option value="">Assign to…</option>
        {staff.map((member) => (
          <option key={member.id} value={member.id}>
            {member.email} · floor {member.floor ?? "—"} · {member.workload} active
          </option>
        ))}
      </select>
      <button className="small-button secondary" disabled={busy || !staffId} onClick={() => run("assign", () => managerApi.assign(task.id, Number(staffId)))}>
        Assign
      </button>
      <button className="small-button danger" disabled={busy} onClick={() => run("cancel", () => managerApi.cancel(task.id))}>
        Cancel
      </button>
      {action.error && <Notice error={action.error} />}
    </div>
  );
}

function StaffRow({ member, onChanged }: { member: StaffMember; onChanged: () => void }) {
  const [floor, setFloor] = useState(member.floor?.toString() ?? "");
  const action = useAction();
  const dirty = floor !== (member.floor?.toString() ?? "");

  async function save(event: FormEvent) {
    event.preventDefault();
    const value = floor.trim() === "" ? null : Number(floor);
    if (value !== null && (!Number.isInteger(value) || value < 0 || value > 200)) {
      action.setError("Floor must be a whole number between 0 and 200.");
      return;
    }
    if (await action.run("save", () => managerApi.setFloor(member.id, value))) onChanged();
  }

  return (
    <form className="staff-row" onSubmit={save}>
      <div className="account-identity">
        <div className="user-avatar">{member.email.slice(0, 1).toUpperCase()}</div>
        <div>
          <strong>{member.email}</strong>
          <span>
            <Badge tone={member.is_available ? "success" : "neutral"}>{member.is_available ? "On shift" : "Off shift"}</Badge>
            {member.workload} active task{member.workload === 1 ? "" : "s"}
          </span>
        </div>
      </div>
      <div className="account-actions">
        <label className="inline-field">
          <span>Floor</span>
          <input className="compact-input" inputMode="numeric" value={floor} onChange={(event) => setFloor(event.target.value)} placeholder="None" />
        </label>
        <button className="small-button" disabled={!dirty || action.busyKey !== null}>Save</button>
      </div>
      {action.error && <Notice error={action.error} />}
    </form>
  );
}

function SettingsForm({ initial, onSaved }: { initial: AssignmentSettings; onSaved: () => void }) {
  const [values, setValues] = useState(initial);
  const action = useAction();

  const fields: Array<{ key: keyof AssignmentSettings; label: string; hint: string; min: number; max: number }> = [
    { key: "adjacent_floor_range", label: "Adjacent floors to search", hint: "0 = requested floor only; 1 = one floor above and below.", min: 0, max: 10 },
    { key: "max_offer_attempts", label: "Offer attempts before escalation", hint: "Declines and timeouts both count as attempts.", min: 1, max: 20 },
    { key: "offer_timeout_seconds", label: "Offer timeout (seconds)", hint: "How long staff have to respond before the next person is offered the task.", min: 30, max: 3600 },
    { key: "max_active_tasks_per_staff", label: "Max active tasks per staff member", hint: "Staff at this limit are not offered new tasks.", min: 1, max: 20 },
  ];

  async function save(event: FormEvent) {
    event.preventDefault();
    for (const field of fields) {
      const value = values[field.key] as number;
      if (!Number.isInteger(value) || value < field.min || value > field.max) {
        action.setError(`${field.label} must be between ${field.min} and ${field.max}.`);
        return;
      }
    }
    const { priority_rules: _rules, ...payload } = values;
    if (await action.run("save", () => managerApi.saveSettings(payload), "Assignment rules saved.")) onSaved();
  }

  return (
    <form className="settings-form" onSubmit={save}>
      {fields.map((field) => (
        <label className="field" key={field.key}>
          <span>{field.label}</span>
          <input
            type="number"
            min={field.min}
            max={field.max}
            value={values[field.key] as number}
            onChange={(event) => setValues({ ...values, [field.key]: Number(event.target.value) })}
          />
          <span className="field-hint">{field.hint}</span>
        </label>
      ))}
      <Notice error={action.error} success={action.success} />
      <button className="primary-button" disabled={action.busyKey !== null}>
        {action.busyKey ? "Saving…" : "Save rules"}
      </button>
      {initial.priority_rules && (
        <div className="rules-box">
          <strong>Priority rules</strong>
          <ul>{initial.priority_rules.map((rule) => <li key={rule}>{rule}</li>)}</ul>
        </div>
      )}
    </form>
  );
}

export default function ManagerDashboard() {
  const [tab, setTab] = useState<Tab>("exceptions");
  const [filter, setFilter] = useState<TaskFilter>("pending");
  const [historyFor, setHistoryFor] = useState<number | null>(null);
  const [floorFilter, setFloorFilter] = useState("");

  const alerts = usePolling(tasksApi.alerts);
  const tasks = usePolling(() => tasksApi.list());
  const staff = usePolling(managerApi.staff);
  const offers = usePolling(managerApi.offers);
  const rooms = usePolling(managerApi.rooms);
  const settings = usePolling(managerApi.settings, 60_000);
  const inspect = useAction();

  const allTasks = tasks.data ?? [];
  const staffList = staff.data ?? [];
  const refreshAll = () => {
    void alerts.refresh();
    void tasks.refresh();
    void staff.refresh();
  };
  const visibleRooms = (rooms.data?.rooms ?? []).filter((room) => !floorFilter || room.floor === Number(floorFilter));
  const floors = [...new Set((rooms.data?.rooms ?? []).map((room) => room.floor))];

  return (
    <PortalLayout wide>
      <div className="dashboard-head">
        <div>
          <p className="eyebrow">Housekeeping</p>
          <h1>Manager dashboard</h1>
          <p className="muted">Allocate staff to floors, monitor workload, and handle escalations. Tasks are offered to staff automatically, so you only act on the alerts.</p>
        </div>
        <LiveIndicator />
      </div>

      <StatGrid
        stats={[
          { label: "Need attention", value: alerts.data?.length ?? "—", tone: alerts.data?.length ? "danger" : "neutral" },
          { label: "Pending", value: allTasks.filter((t) => matchesFilter(t, "pending")).length, tone: "warning" },
          { label: "In progress", value: allTasks.filter((t) => t.status === "in_progress").length, tone: "progress" },
          { label: "Staff on shift", value: staffList.filter((s) => s.is_available).length },
          { label: "Rooms ready", value: rooms.data?.summary.ready ?? "—", tone: "success" },
        ]}
      />

      <div className="tabs" role="tablist">
        {(Object.keys(tabLabels) as Tab[]).map((name) => (
          <button key={name} role="tab" aria-selected={tab === name} className={tab === name ? "tab active" : "tab"} onClick={() => setTab(name)}>
            {tabLabels[name]}
            {name === "exceptions" && !!alerts.data?.length && <span className="tab-count">{alerts.data.length}</span>}
          </button>
        ))}
      </div>

      {tab === "exceptions" && (
        <Panel title="Tasks that could not be assigned" description="Retry automatic assignment, assign a staff member directly, or cancel.">
          <Notice error={alerts.error} />
          {alerts.loading ? <LoadingState /> : !alerts.data?.length ? (
            <EmptyState>All clear. Every open task has an owner or an active offer.</EmptyState>
          ) : (
            <div className="exception-list">
              {alerts.data.map((task) => (
                <article className="exception-card" key={task.id}>
                  <div className="exception-info">
                    <strong>{serviceLabels[task.service]} · Room {task.room_number}</strong>
                    <small>{task.reference} · floor {task.floor} · {task.attempts} offer(s) · created {formatTime(task.created_at)}</small>
                    <span className="alert-text">{task.alert_reason}</span>
                  </div>
                  <ExceptionActions task={task} staff={staffList} onDone={refreshAll} />
                </article>
              ))}
            </div>
          )}
        </Panel>
      )}

      {tab === "tasks" && (
        <Panel
          title="Task monitor"
          actions={
            <div className="chip-row">
              {(Object.keys(filterLabels) as TaskFilter[]).map((name) => (
                <button key={name} className={filter === name ? "chip active" : "chip"} onClick={() => setFilter(name)}>
                  {filterLabels[name]} ({allTasks.filter((t) => matchesFilter(t, name)).length})
                </button>
              ))}
            </div>
          }
        >
          <Notice error={tasks.error} />
          {tasks.loading ? <LoadingState /> : (() => {
            const visible = allTasks.filter((t) => matchesFilter(t, filter));
            return visible.length === 0 ? <EmptyState>No {filterLabels[filter].toLowerCase()} tasks.</EmptyState> : (
              <TaskTable
                tasks={visible}
                showAssignee
                renderActions={(task) => (
                  <button className="small-button secondary" onClick={() => setHistoryFor(historyFor === task.id ? null : task.id)}>
                    {historyFor === task.id ? "Hide" : "History"}
                  </button>
                )}
              />
            );
          })()}
          {historyFor && <TaskHistory taskId={historyFor} onClose={() => setHistoryFor(null)} />}
        </Panel>
      )}

      {tab === "staff" && (
        <Panel title="Staff allocation" description="Staff receive offers for their floor, then permitted adjacent floors. Only staff on shift receive offers.">
          <Notice error={staff.error} />
          {staff.loading ? <LoadingState /> : staffList.length === 0 ? (
            <EmptyState>No active housekeeping staff yet. Staff appear here after they create an account.</EmptyState>
          ) : (
            <div className="account-list">
              {staffList.map((member) => (
                <StaffRow key={`${member.id}-${member.floor}`} member={member} onChanged={staff.refresh} />
              ))}
            </div>
          )}
        </Panel>
      )}

      {tab === "offers" && (
        <Panel title="Declined and timed-out offers" description="The system re-offers these automatically until the attempt limit is reached.">
          <Notice error={offers.error} />
          {offers.loading ? <LoadingState /> : !offers.data?.length ? <EmptyState>No declined or timed-out offers.</EmptyState> : (
            <div className="simple-list">
              {offers.data.map((offer) => (
                <div className="simple-row" key={offer.id}>
                  <span>
                    <strong>{serviceLabels[offer.service]} · Room {offer.room_number}</strong>
                    <small>{offer.reference} · {offer.staff}</small>
                  </span>
                  <span className="simple-row-meta">
                    <Badge tone={offer.outcome === "declined" ? "warning" : "danger"}>{offer.outcome === "declined" ? "Declined" : "Timed out"}</Badge>
                    <small>{formatTime(offer.responded_at)}</small>
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      )}

      {tab === "rooms" && (
        <Panel
          title="Room readiness"
          description="Rooms move to Awaiting Inspection when cleaning is completed. Mark them ready after inspection."
          actions={
            <select className="compact-select" value={floorFilter} onChange={(event) => setFloorFilter(event.target.value)} aria-label="Filter by floor">
              <option value="">All floors</option>
              {floors.map((floor) => <option key={floor} value={floor}>Floor {floor}</option>)}
            </select>
          }
        >
          <Notice error={rooms.error || inspect.error} />
          {rooms.data && (
            <div className="chip-row summary-chips">
              {(Object.keys(roomStatusLabels) as RoomStatus[]).map((status) => (
                <span key={status} className="summary-chip"><RoomStatusBadge status={status} /> {rooms.data!.summary[status]}</span>
              ))}
            </div>
          )}
          {rooms.loading ? <LoadingState /> : visibleRooms.length === 0 ? (
            <EmptyState>No rooms found. Load demo rooms with <code>python -m app.demo_seed</code>.</EmptyState>
          ) : (
            <div className="room-grid">
              {visibleRooms.map((room) => (
                <div className={`room-tile room-${room.status}`} key={room.id}>
                  <strong>{room.number}</strong>
                  <RoomStatusBadge status={room.status} />
                  {room.status === "awaiting_inspection" && (
                    <button
                      className="small-button"
                      disabled={inspect.busyKey === String(room.id)}
                      onClick={async () => {
                        if (await inspect.run(String(room.id), () => managerApi.inspect(room.id))) void rooms.refresh();
                      }}
                    >
                      Mark ready
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </Panel>
      )}

      {tab === "settings" && (
        <Panel title="Assignment rules" description="Changes apply to the next offer the system makes.">
          <Notice error={settings.error} />
          {settings.loading || !settings.data ? <LoadingState /> : <SettingsForm key={JSON.stringify(settings.data)} initial={settings.data} onSaved={settings.refresh} />}
        </Panel>
      )}
    </PortalLayout>
  );
}
