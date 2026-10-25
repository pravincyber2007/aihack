import { useEffect, useState, type FormEvent } from "react";
import { receptionApi } from "../api/client";
import { PortalLayout } from "../components/PortalLayout";
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
  TaskStatusBadge,
  TaskTable,
  useAction,
  usePolling,
} from "../components/ui";
import {
  roomStatusLabels,
  serviceLabels,
  type OccupancyFilter,
  type RoomWithRequests,
  type ServiceType,
} from "../types";

const services = Object.keys(serviceLabels) as ServiceType[];
const filterLabels: Record<OccupancyFilter, string> = {
  all: "All rooms",
  available: "Available",
  occupied: "Occupied",
};

function phoneIsValid(value: string) {
  return /^\d{8,15}$/.test(value.replace(/[\s().-]/g, "").replace(/^\+/, ""));
}

function OccupancyBadge({ room }: { room: RoomWithRequests }) {
  if (room.occupancy) return <Badge tone="info">Occupied</Badge>;
  if (room.available) return <Badge tone="success">Available</Badge>;
  return <Badge tone="warning">Not ready</Badge>;
}

function CheckInForm({ room, onDone }: { room: RoomWithRequests; onDone: (room: RoomWithRequests) => void }) {
  const [guestName, setGuestName] = useState("");
  const [phone, setPhone] = useState("");
  const [nights, setNights] = useState("1");
  const action = useAction();

  async function submit(event: FormEvent) {
    event.preventDefault();
    const nightCount = Number(nights);
    if (!guestName.trim()) return action.setError("Enter the guest's name.");
    if (!phoneIsValid(phone)) return action.setError("Enter a valid phone number, including the country or area code.");
    if (!Number.isInteger(nightCount) || nightCount < 1 || nightCount > 60) {
      return action.setError("Nights must be a whole number from 1 to 60.");
    }
    let updated: RoomWithRequests | null = null;
    const ok = await action.run("checkin", async () => {
      updated = await receptionApi.checkIn({ room_number: room.number, guest_name: guestName, phone, nights: nightCount });
    });
    if (ok && updated) onDone(updated);
  }

  return (
    <form className="form tight" onSubmit={submit}>
      <label className="field">
        <span>Guest name</span>
        <input value={guestName} onChange={(event) => setGuestName(event.target.value)} maxLength={120} autoComplete="off" required />
      </label>
      <label className="field">
        <span>Phone number</span>
        <input type="tel" value={phone} onChange={(event) => setPhone(event.target.value)} maxLength={30} placeholder="e.g. +91 98765 43210" autoComplete="off" required />
        <span className="field-hint">The guest uses this number to open their room services.</span>
      </label>
      <label className="field">
        <span>Nights</span>
        <input type="number" min={1} max={60} value={nights} onChange={(event) => setNights(event.target.value)} required />
      </label>
      <Notice error={action.error} />
      <button className="primary-button" disabled={action.busyKey !== null}>
        {action.busyKey ? "Checking in…" : `Check in to room ${room.number}`}
      </button>
    </form>
  );
}

function CheckOutCard({ room, onDone }: { room: RoomWithRequests; onDone: (room: RoomWithRequests) => void }) {
  const [confirming, setConfirming] = useState(false);
  const action = useAction();
  const stay = room.occupancy!;

  async function checkOut() {
    let updated: RoomWithRequests | null = null;
    const ok = await action.run("checkout", async () => {
      updated = await receptionApi.checkOut(room.number);
    });
    if (ok && updated) onDone(updated);
  }

  return (
    <div className="stay-card">
      <div className="stay-details">
        <strong>{stay.guest_name}</strong>
        <small>Phone ending •••• {stay.phone_last4}</small>
        <small>Checked in {formatTime(stay.check_in_at)} · checks out {formatTime(stay.check_out_at)}</small>
      </div>
      <Notice error={action.error} />
      {confirming ? (
        <div className="confirm-row">
          <span>Check out {stay.guest_name}? Room services stop and a cleaning task is created.</span>
          <div className="confirm-actions">
            <button className="small-button secondary" onClick={() => setConfirming(false)} disabled={action.busyKey !== null}>Keep stay</button>
            <button className="small-button danger" onClick={checkOut} disabled={action.busyKey !== null}>
              {action.busyKey ? "Checking out…" : "Confirm check-out"}
            </button>
          </div>
        </div>
      ) : (
        <button className="small-button danger big-inline" onClick={() => setConfirming(true)}>Check out guest</button>
      )}
    </div>
  );
}

function RequestForm({ room, onCreated }: { room: RoomWithRequests; onCreated: () => void }) {
  const [service, setService] = useState<ServiceType>("cleaning");
  const [instructions, setInstructions] = useState("");
  const [urgent, setUrgent] = useState(false);
  const action = useAction();

  async function submit(event: FormEvent) {
    event.preventDefault();
    let reference = "";
    const ok = await action.run("submit", async () => {
      reference = (await receptionApi.submit({ room_number: room.number, service, instructions, urgent })).reference;
    });
    if (ok) {
      action.setSuccess(`Request ${reference} created for room ${room.number}.`);
      setInstructions("");
      setUrgent(false);
      onCreated();
    }
  }

  return (
    <form className="form tight" onSubmit={submit}>
      <label className="field">
        <span>Service</span>
        <select value={service} onChange={(event) => setService(event.target.value as ServiceType)}>
          {services.map((option) => <option key={option} value={option}>{serviceLabels[option]}</option>)}
        </select>
      </label>
      <label className="field">
        <span>Instructions (optional)</span>
        <textarea value={instructions} onChange={(event) => setInstructions(event.target.value)} maxLength={500} rows={3} placeholder="e.g. Guest prefers service after 2pm" />
      </label>
      <label className="checkbox-field">
        <input type="checkbox" checked={urgent} onChange={(event) => setUrgent(event.target.checked)} />
        <span>Mark as urgent</span>
      </label>
      <Notice error={action.error} success={action.success} />
      <button className="primary-button" disabled={action.busyKey !== null}>
        {action.busyKey ? "Submitting…" : "Submit request"}
      </button>
    </form>
  );
}

export default function ReceptionDashboard() {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<OccupancyFilter>("all");
  const [selected, setSelected] = useState<RoomWithRequests | null>(null);
  const [notice, setNotice] = useState("");
  const rooms = usePolling(() => receptionApi.rooms(query, filter));
  const summary = usePolling(receptionApi.summary);
  const requests = usePolling(receptionApi.requests);

  // Re-run the search immediately when the query or filter changes.
  useEffect(() => {
    void rooms.refresh();
  }, [query, filter]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep the selected room's details current as the list refreshes.
  useEffect(() => {
    const fresh = rooms.data?.find((room) => room.id === selected?.id);
    if (fresh) setSelected(fresh);
  }, [rooms.data]); // eslint-disable-line react-hooks/exhaustive-deps

  function refreshAll() {
    void rooms.refresh();
    void summary.refresh();
    void requests.refresh();
  }

  function afterStayChange(updated: RoomWithRequests, message: string) {
    setSelected(updated);
    setNotice(message);
    refreshAll();
  }

  return (
    <PortalLayout wide>
      <div className="dashboard-head">
        <div>
          <p className="eyebrow">Front desk</p>
          <h1>Reception dashboard</h1>
        </div>
        <LiveIndicator />
      </div>

      <StatGrid
        stats={[
          { label: "Available to check in", value: summary.data?.available ?? "—", tone: "success" },
          { label: "Occupied", value: summary.data?.occupied ?? "—", tone: "progress" },
          { label: "Being cleaned / inspected", value: summary.data?.needs_cleaning ?? "—", tone: "warning" },
          { label: "Total rooms", value: summary.data?.total ?? "—" },
        ]}
      />

      <div className="two-column">
        <Panel title="Rooms" description="Select a room to check a guest in or out, or to submit a housekeeping request.">
          <input
            className="search-input"
            value={query}
            onChange={(event) => setQuery(event.target.value.replace(/[^0-9A-Za-z]/g, ""))}
            placeholder="Room number, e.g. 305"
            aria-label="Search room number"
            maxLength={10}
          />
          <div className="chip-row filter-row">
            {(Object.keys(filterLabels) as OccupancyFilter[]).map((name) => (
              <button key={name} className={filter === name ? "chip active" : "chip"} onClick={() => setFilter(name)}>
                {filterLabels[name]}
              </button>
            ))}
          </div>
          <Notice error={rooms.error} />
          {rooms.loading ? <LoadingState /> : !rooms.data?.length ? (
            <EmptyState>No {filter === "all" ? "" : filterLabels[filter].toLowerCase() + " "}rooms match{query ? ` “${query}”` : ""}.</EmptyState>
          ) : (
            <div className="room-results">
              {rooms.data.map((room) => (
                <button
                  type="button"
                  key={room.id}
                  className={selected?.id === room.id ? "room-result selected" : "room-result"}
                  onClick={() => {
                    setSelected(room);
                    setNotice("");
                  }}
                >
                  <span className="room-result-head">
                    <strong>Room {room.number}</strong>
                    <span><OccupancyBadge room={room} /><RoomStatusBadge status={room.status} /></span>
                  </span>
                  <small>
                    Floor {room.floor}
                    {room.occupancy && ` · ${room.occupancy.guest_name} · until ${formatTime(room.occupancy.check_out_at)}`}
                  </small>
                  {room.open_requests.map((task) => (
                    <span className="room-request" key={task.id}>
                      {serviceLabels[task.service]} <TaskStatusBadge status={task.status} />
                    </span>
                  ))}
                </button>
              ))}
            </div>
          )}
        </Panel>

        <div>
          {!selected ? (
            <Panel title="Select a room" description="Choose a room from the list to manage it.">
              <EmptyState>Pick an <strong>Available</strong> room to check a guest in, or an <strong>Occupied</strong> room to check out.</EmptyState>
            </Panel>
          ) : (
            <>
              <Panel
                title={`Room ${selected.number}`}
                description={`Floor ${selected.floor} · ${roomStatusLabels[selected.status]}`}
                actions={<OccupancyBadge room={selected} />}
              >
                <Notice success={notice} />
                {selected.occupancy ? (
                  <CheckOutCard key={`out-${selected.id}`} room={selected} onDone={(room) => afterStayChange(room, `Guest checked out of room ${room.number}. A cleaning task has been sent to housekeeping.`)} />
                ) : selected.available ? (
                  <CheckInForm key={`in-${selected.id}`} room={selected} onDone={(room) => afterStayChange(room, `${room.occupancy?.guest_name} is checked in to room ${room.number}. They can now use Continue as Guest with their phone number.`)} />
                ) : (
                  <EmptyState>
                    This room is <strong>{roomStatusLabels[selected.status]}</strong> and can't be checked in yet.
                    It becomes available once housekeeping finishes and the manager marks it ready.
                  </EmptyState>
                )}
              </Panel>
              <Panel title="Housekeeping request" description={`For room ${selected.number}. Staff are assigned automatically.`}>
                <RequestForm key={`req-${selected.id}`} room={selected} onCreated={refreshAll} />
              </Panel>
            </>
          )}
        </div>
      </div>

      <Panel title="Request progress" description="Estimated completion is shown only when there is enough recent history for that service to be reliable.">
        <Notice error={requests.error} />
        {requests.loading ? <LoadingState /> : !requests.data?.length ? (
          <EmptyState>No requests yet.</EmptyState>
        ) : (
          <TaskTable tasks={requests.data} showEta />
        )}
      </Panel>
    </PortalLayout>
  );
}
