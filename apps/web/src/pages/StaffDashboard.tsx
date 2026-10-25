import { useEffect, useState } from "react";
import { staffApi } from "../api/client";
import { PortalLayout } from "../components/PortalLayout";
import {
  Badge,
  EmptyState,
  formatTime,
  LiveIndicator,
  LoadingState,
  Notice,
  PriorityBadge,
  TaskStatusBadge,
  timeUntil,
  useAction,
  usePolling,
} from "../components/ui";
import { serviceLabels, type Task } from "../types";

function TaskDetails({ task }: { task: Task }) {
  return (
    <>
      <div className="mobile-card-head">
        <div>
          <span className="room-number">Room {task.room_number}</span>
          <small>Floor {task.floor} · {task.reference}</small>
        </div>
        <PriorityBadge priority={task.priority} />
      </div>
      <strong className="mobile-card-title">{serviceLabels[task.service]}</strong>
      {task.instructions ? <p className="instructions">“{task.instructions}”</p> : <p className="instructions muted-text">No special instructions</p>}
    </>
  );
}

/** Re-renders every second so offer countdowns stay current. */
function useTicker() {
  const [, setTick] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setTick((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, []);
}

export default function StaffDashboard() {
  useTicker();
  const shift = usePolling(staffApi.me);
  const offers = usePolling(staffApi.offers);
  const tasks = usePolling(staffApi.tasks);
  const action = useAction();

  const refresh = () => {
    void offers.refresh();
    void tasks.refresh();
  };
  // Refresh after failures too: a conflict usually means the offer already moved on.
  const run = async (key: string, fn: () => Promise<unknown>, message: string) => {
    await action.run(key, fn, message);
    refresh();
  };

  const myTasks = tasks.data ?? [];
  const active = myTasks.filter((task) => task.status !== "completed");
  const completed = myTasks.filter((task) => task.status === "completed");
  const overdue = active.filter((task) => task.overdue).length;

  return (
    <PortalLayout>
      <div className="dashboard-head">
        <div>
          <p className="eyebrow">Housekeeping staff</p>
          <h1>My tasks</h1>
        </div>
        <LiveIndicator />
      </div>

      <section className="shift-card">
        <div>
          <strong>{shift.data?.floor != null ? `Floor ${shift.data.floor}` : "No floor allocated yet"}</strong>
          <small>
            {shift.data?.floor == null
              ? "Your manager needs to allocate you to a floor before you receive offers."
              : shift.data.is_available
                ? "You are on shift and can receive new task offers."
                : "You are off shift. Go on shift to receive offers."}
          </small>
        </div>
        <button
          className={shift.data?.is_available ? "toggle on" : "toggle"}
          role="switch"
          aria-checked={!!shift.data?.is_available}
          disabled={!shift.data || action.busyKey === "shift"}
          onClick={async () => {
            if (await action.run("shift", () => staffApi.setAvailability(!shift.data?.is_available))) void shift.refresh();
          }}
        >
          {shift.data?.is_available ? "On shift" : "Off shift"}
        </button>
      </section>

      <div className="mini-stats">
        <span><strong>{offers.data?.length ?? 0}</strong> new offers</span>
        <span><strong>{active.length}</strong> pending</span>
        <span className={overdue ? "danger-text" : ""}><strong>{overdue}</strong> overdue</span>
      </div>

      <Notice error={action.error || offers.error || tasks.error} success={action.success} />

      <h2 className="section-title">New offers</h2>
      {offers.loading ? <LoadingState /> : !offers.data?.length ? (
        <EmptyState>No new offers right now. New tasks appear here automatically.</EmptyState>
      ) : (
        <div className="mobile-list">
          {offers.data.map((offer) => (
            <article className="mobile-card offer-card" key={offer.offer_id}>
              <TaskDetails task={offer.task} />
              <small className="countdown">Respond within {timeUntil(offer.expires_at)}</small>
              <div className="mobile-actions">
                <button className="small-button secondary big" disabled={action.busyKey !== null} onClick={() => run(`decline-${offer.offer_id}`, () => staffApi.decline(offer.offer_id), "Offer declined.")}>
                  Decline
                </button>
                <button className="small-button big" disabled={action.busyKey !== null} onClick={() => run(`accept-${offer.offer_id}`, () => staffApi.accept(offer.offer_id), "Task accepted. It's now in your assigned tasks.")}>
                  {action.busyKey === `accept-${offer.offer_id}` ? "Accepting…" : "Accept"}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      <h2 className="section-title">Assigned to me</h2>
      {tasks.loading ? <LoadingState /> : active.length === 0 ? (
        <EmptyState>You have no assigned tasks.</EmptyState>
      ) : (
        <div className="mobile-list">
          {active.map((task) => (
            <article className={task.overdue ? "mobile-card overdue" : "mobile-card"} key={task.id}>
              <TaskDetails task={task} />
              <div className="mobile-card-meta">
                <TaskStatusBadge status={task.status} />
                {task.overdue ? <Badge tone="danger">Overdue</Badge> : <small>Due {formatTime(task.due_at)}</small>}
              </div>
              <div className="mobile-actions">
                {task.status === "accepted" && (
                  <button className="small-button big" disabled={action.busyKey !== null} onClick={() => run(`start-${task.id}`, () => staffApi.start(task.id), "Task started.")}>
                    Start task
                  </button>
                )}
                {task.status === "in_progress" && (
                  <button className="small-button big" disabled={action.busyKey !== null} onClick={() => run(`complete-${task.id}`, () => staffApi.complete(task.id), "Task completed. Nice work!")}>
                    Mark completed
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}

      {completed.length > 0 && (
        <>
          <h2 className="section-title">Completed in the last 24 hours</h2>
          <div className="simple-list">
            {completed.map((task) => (
              <div className="simple-row" key={task.id}>
                <span><strong>Room {task.room_number} · {serviceLabels[task.service]}</strong><small>{task.reference}</small></span>
                <small>{formatTime(task.completed_at)}</small>
              </div>
            ))}
          </div>
        </>
      )}
    </PortalLayout>
  );
}
