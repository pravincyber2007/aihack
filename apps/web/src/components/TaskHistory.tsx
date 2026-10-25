import { tasksApi } from "../api/client";
import { formatTime, LoadingState, Notice, usePolling } from "./ui";

const eventLabels: Record<string, string> = {
  created: "Created",
  offered: "Offered",
  accepted: "Accepted",
  declined: "Declined",
  timed_out: "Timed out",
  unassignable: "No eligible staff",
  escalated: "Escalated",
  retried: "Retried",
  assigned: "Assigned by manager",
  started: "Started",
  completed: "Completed",
  cancelled: "Cancelled",
};

export function TaskHistory({ taskId, onClose }: { taskId: number; onClose: () => void }) {
  const history = usePolling(() => tasksApi.history(taskId));

  return (
    <div className="history-box">
      <div className="history-head">
        <strong>Assignment history {history.data ? `· ${history.data.reference}` : ""}</strong>
        <button className="text-button" onClick={onClose}>Close</button>
      </div>
      <Notice error={history.error} />
      {history.loading ? <LoadingState /> : (
        <ol className="timeline">
          {history.data?.events.map((entry, index) => (
            <li key={index}>
              <span className="timeline-time">{formatTime(entry.created_at)}</span>
              <span>
                <strong>{eventLabels[entry.event] ?? entry.event}</strong>
                {entry.detail && <small> — {entry.detail}</small>}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
