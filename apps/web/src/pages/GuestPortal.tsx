import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { guestApi } from "../api/client";
import { EmptyState, formatTime, Notice, usePolling } from "../components/ui";
import { serviceLabels, type GuestRequest, type GuestRoom, type ServiceType } from "../types";

const serviceIcons: Record<ServiceType, string> = {
  cleaning: "🧹",
  towels: "🛁",
  toiletries: "🧴",
  water: "💧",
  pillows: "🛏️",
  issue: "🔧",
  other: "💬",
};

const statusSteps = ["Submitted", "Pending Assignment", "Accepted", "In Progress", "Completed"];

function newRequestId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}

function phoneIsValid(value: string) {
  const digits = value.replace(/[\s().-]/g, "").replace(/^\+/, "");
  return /^\d{8,15}$/.test(digits);
}

function GuestShell({ children }: { children: ReactNode }) {
  return (
    <main className="guest-shell">
      <div className="guest-card">{children}</div>
      <Link className="guest-staff-link" to="/login">Staff sign in</Link>
    </main>
  );
}

function PhoneStep({ onMatched }: { onMatched: (room: GuestRoom) => void }) {
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!phoneIsValid(phone)) {
      setError("Enter a valid phone number, including the country or area code.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      onMatched(await guestApi.access(phone));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="guest-form" onSubmit={submit} noValidate>
      <h1>Access Your Room Services</h1>
      <label className="sr-only" htmlFor="guest-phone">Phone number</label>
      <input
        id="guest-phone"
        className="guest-input"
        type="tel"
        inputMode="tel"
        autoComplete="tel"
        placeholder="Enter your registered phone number"
        value={phone}
        onChange={(event) => setPhone(event.target.value)}
        maxLength={30}
      />
      <Notice error={error} />
      <button className="primary-button" disabled={busy}>{busy ? "Submitting…" : "Submit"}</button>
    </form>
  );
}

function RequestStatus({ request }: { request: GuestRequest }) {
  const current = statusSteps.indexOf(request.status);
  return (
    <article className="guest-request">
      <div className="guest-request-head">
        <strong>{serviceIcons[request.service]} {serviceLabels[request.service]}</strong>
        <small>{request.reference}</small>
      </div>
      {request.status === "Cancelled" ? (
        <p className="feedback error">This request was cancelled. Please contact the front desk if you still need help.</p>
      ) : (
        <ol className="status-steps" aria-label={`Status: ${request.status}`}>
          {statusSteps.map((step, index) => (
            <li key={step} className={index < current ? "done" : index === current ? "current" : ""}>{step}</li>
          ))}
        </ol>
      )}
      <small className="muted-text">
        Requested {formatTime(request.created_at)}
        {request.completed_at && ` · completed ${formatTime(request.completed_at)}`}
        {request.estimated_completion_at && ` · estimated by ${formatTime(request.estimated_completion_at)}`}
      </small>
    </article>
  );
}

function ServicesStep({ room, onSignOut }: { room: GuestRoom; onSignOut: () => void }) {
  const [selected, setSelected] = useState<ServiceType | null>(null);
  const [instructions, setInstructions] = useState("");
  const [requestId, setRequestId] = useState(newRequestId);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmation, setConfirmation] = useState<GuestRequest | null>(null);
  const requests = usePolling(guestApi.requests);

  function choose(service: ServiceType) {
    setSelected(service);
    setInstructions("");
    setError("");
    setConfirmation(null);
    setRequestId(newRequestId());
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selected || busy) return;
    setBusy(true);
    setError("");
    try {
      // The same request ID is reused on retries so repeated taps never create duplicates.
      const created = await guestApi.submit({ service: selected, instructions, client_request_id: requestId });
      setConfirmation(created);
      setSelected(null);
      void requests.refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not submit your request. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="guest-services">
      <div className="guest-welcome">
        <h1>Welcome! Room {room.room_number}</h1>
        <button className="text-button" onClick={onSignOut}>Sign out</button>
      </div>

      {confirmation && (
        <p className="feedback success" role="status">
          Request received! Your request ID is <strong>{confirmation.reference}</strong>. You can follow its progress below.
        </p>
      )}

      {selected ? (
        <form className="guest-form" onSubmit={submit}>
          <h2>{serviceIcons[selected]} {serviceLabels[selected]}</h2>
          <label className="field">
            <span>Instructions (optional)</span>
            <textarea value={instructions} onChange={(event) => setInstructions(event.target.value)} maxLength={500} rows={3} placeholder="Anything we should know?" />
          </label>
          <Notice error={error} />
          <button className="primary-button" disabled={busy}>{busy ? "Submitting…" : "Submit Request"}</button>
          <button type="button" className="text-button" onClick={() => setSelected(null)} disabled={busy}>Back to services</button>
        </form>
      ) : (
        <div className="service-grid">
          {room.services.map((service) => (
            <button key={service} className="service-card" onClick={() => choose(service)}>
              <span className="service-icon" aria-hidden="true">{serviceIcons[service]}</span>
              <span>{service === "issue" ? "Report a Room Issue" : service === "other" ? "Other Request" : `Request ${serviceLabels[service]}`}</span>
            </button>
          ))}
        </div>
      )}

      <h2 className="section-title">My requests</h2>
      <Notice error={requests.error} />
      {requests.loading ? null : !requests.data?.length ? (
        <EmptyState>You haven't made any requests during this stay.</EmptyState>
      ) : (
        <div className="guest-request-list">
          {requests.data.map((request) => <RequestStatus key={request.id} request={request} />)}
        </div>
      )}
    </div>
  );
}

export default function GuestPortal() {
  const [step, setStep] = useState<"checking" | "phone" | "services">("checking");
  const [room, setRoom] = useState<GuestRoom | null>(null);

  useEffect(() => {
    guestApi
      .me()
      .then((current) => {
        setRoom(current);
        setStep("services");
      })
      .catch(() => setStep("phone"));
  }, []);

  async function signOut() {
    await guestApi.logout().catch(() => undefined);
    setRoom(null);
    setStep("phone");
  }

  if (step === "checking") return <div className="loading">Loading…</div>;
  return (
    <GuestShell>
      {step === "phone" && <PhoneStep onMatched={(matched) => { setRoom(matched); setStep("services"); }} />}
      {step === "services" && room && <ServicesStep room={room} onSignOut={signOut} />}
    </GuestShell>
  );
}
