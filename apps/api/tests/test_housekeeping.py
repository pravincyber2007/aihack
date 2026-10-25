from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    GuestStay,
    OfferStatus,
    Room,
    RoomStatus,
    Task,
    TaskOffer,
    TaskStatus,
    UserRole,
)
from app.services.assignment import utcnow
from app.services.guest_access import reset_lookup_limits


@pytest.fixture
def hotel(db_session: Session) -> dict[str, Room]:
    rooms = {
        number: Room(number=number, floor=int(number[0]), status=RoomStatus.READY)
        for number in ("201", "305", "306", "501")
    }
    db_session.add_all(rooms.values())
    db_session.commit()
    return rooms


@pytest.fixture(autouse=True)
def fresh_lookup_limits():
    reset_lookup_limits()
    yield
    reset_lookup_limits()


def _reception_request(client, csrf, room="305", service="towels", **extra) -> dict:
    response = client.post(
        "/api/v1/reception/requests",
        headers=csrf,
        json={"room_number": room, "service": service, **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _pending_offer(db: Session, task_id: int) -> TaskOffer | None:
    db.expire_all()
    return db.scalar(
        select(TaskOffer).where(TaskOffer.task_id == task_id, TaskOffer.status == OfferStatus.PENDING)
    )


def test_offer_goes_to_same_floor_then_least_busy_and_only_one_owner(
    client: TestClient, db_session: Session, csrf_headers, hotel, make_user, login_as
) -> None:
    make_user("desk@example.com", UserRole.RECEPTIONIST)
    near = make_user("near@example.com", UserRole.HOUSEKEEPING_STAFF, floor=3, available=True)
    make_user("adjacent@example.com", UserRole.HOUSEKEEPING_STAFF, floor=4, available=True)
    make_user("offshift@example.com", UserRole.HOUSEKEEPING_STAFF, floor=3, available=False)

    login_as("desk@example.com")
    task = _reception_request(client, csrf_headers)
    offer = _pending_offer(db_session, task["id"])
    assert offer.staff_id == near.id

    login_as("near@example.com")
    offers = client.get("/api/v1/staff/offers").json()
    assert [o["task"]["room_number"] for o in offers] == ["305"]
    accepted = client.post(f"/api/v1/staff/offers/{offer.id}/accept", headers=csrf_headers)
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    again = client.post(f"/api/v1/staff/offers/{offer.id}/accept", headers=csrf_headers)
    assert again.status_code == 409

    # Second request on floor 3: "near" now has one active task, so the adjacent,
    # idle staff member on floor 4 is still farther away and "near" stays first.
    login_as("desk@example.com")
    second = _reception_request(client, csrf_headers, room="306", service="water")
    assert _pending_offer(db_session, second["id"]).staff_id == near.id


def test_decline_and_timeout_move_to_next_candidate_then_escalate(
    client: TestClient, db_session: Session, csrf_headers, hotel, make_user, login_as
) -> None:
    make_user("desk@example.com", UserRole.RECEPTIONIST)
    first = make_user("first@example.com", UserRole.HOUSEKEEPING_STAFF, floor=3, available=True)
    second = make_user("second@example.com", UserRole.HOUSEKEEPING_STAFF, floor=2, available=True)
    make_user("boss@example.com", UserRole.HOUSEKEEPING_MANAGER)

    login_as("desk@example.com")
    task = _reception_request(client, csrf_headers)
    offer = _pending_offer(db_session, task["id"])
    assert offer.staff_id == first.id

    login_as("first@example.com")
    assert client.post(f"/api/v1/staff/offers/{offer.id}/decline", headers=csrf_headers).status_code == 200
    offer = _pending_offer(db_session, task["id"])
    assert offer.staff_id == second.id

    # Let the second offer time out; the next poll should process it.
    db_session.execute(
        update(TaskOffer).where(TaskOffer.id == offer.id).values(expires_at=utcnow() - timedelta(seconds=1))
    )
    db_session.commit()
    login_as("boss@example.com")
    alerts = client.get("/api/v1/tasks/alerts").json()
    assert [a["id"] for a in alerts] == [task["id"]]
    assert alerts[0]["status"] == "pending_assignment"
    outcomes = {o["outcome"] for o in client.get("/api/v1/manager/offers").json()}
    assert outcomes == {"declined", "expired"}

    # After a retry, both are eligible again; with a limit of 1 attempt the next
    # decline escalates instead of offering again.
    client.put(
        "/api/v1/manager/settings",
        headers=csrf_headers,
        json={"adjacent_floor_range": 1, "max_offer_attempts": 1, "offer_timeout_seconds": 60, "max_active_tasks_per_staff": 3},
    )
    assert client.post(f"/api/v1/manager/tasks/{task['id']}/retry", headers=csrf_headers).status_code == 200
    offer = _pending_offer(db_session, task["id"])
    staff_email = "first@example.com" if offer.staff_id == first.id else "second@example.com"
    login_as(staff_email)
    client.post(f"/api/v1/staff/offers/{offer.id}/decline", headers=csrf_headers)
    db_session.expire_all()
    assert db_session.get(Task, task["id"]).status == TaskStatus.ESCALATED

    login_as("boss@example.com")
    assigned = client.post(
        f"/api/v1/manager/tasks/{task['id']}/assign", headers=csrf_headers, json={"staff_id": second.id}
    )
    assert assigned.status_code == 200
    db_session.expire_all()
    assert db_session.get(Task, task["id"]).assigned_to_id == second.id


def test_adjacent_floor_limit_is_respected(
    client: TestClient, db_session: Session, csrf_headers, hotel, make_user, login_as
) -> None:
    make_user("desk@example.com", UserRole.RECEPTIONIST)
    make_user("far@example.com", UserRole.HOUSEKEEPING_STAFF, floor=5, available=True)
    login_as("desk@example.com")
    task = _reception_request(client, csrf_headers)  # floor 3, staff two floors away
    db_session.expire_all()
    stored = db_session.get(Task, task["id"])
    assert stored.status == TaskStatus.PENDING_ASSIGNMENT
    assert "floor 3" in stored.alert_reason


def test_staff_task_lifecycle_updates_room_readiness(
    client: TestClient, db_session: Session, csrf_headers, hotel, make_user, login_as
) -> None:
    make_user("desk@example.com", UserRole.RECEPTIONIST)
    make_user("cleaner@example.com", UserRole.HOUSEKEEPING_STAFF, floor=3, available=True)
    make_user("other@example.com", UserRole.HOUSEKEEPING_STAFF, floor=3, available=False)
    make_user("boss@example.com", UserRole.HOUSEKEEPING_MANAGER)

    login_as("desk@example.com")
    task = _reception_request(client, csrf_headers, service="cleaning", urgent=True)
    assert task["priority"] == "urgent"
    rooms = client.get("/api/v1/reception/rooms?query=305").json()
    assert rooms[0]["status"] == "cleaning_required"
    assert rooms[0]["open_requests"][0]["estimated_completion_at"] is None

    login_as("other@example.com")
    assert client.post(f"/api/v1/staff/tasks/{task['id']}/start", headers=csrf_headers).status_code == 404

    login_as("cleaner@example.com")
    offer_id = client.get("/api/v1/staff/offers").json()[0]["offer_id"]
    client.post(f"/api/v1/staff/offers/{offer_id}/accept", headers=csrf_headers)
    assert client.post(f"/api/v1/staff/tasks/{task['id']}/complete", headers=csrf_headers).status_code == 409
    assert client.post(f"/api/v1/staff/tasks/{task['id']}/start", headers=csrf_headers).status_code == 200
    db_session.expire_all()
    assert db_session.get(Room, hotel["305"].id).status == RoomStatus.CLEANING_IN_PROGRESS
    assert client.post(f"/api/v1/staff/tasks/{task['id']}/complete", headers=csrf_headers).status_code == 200

    login_as("boss@example.com")
    room_id = hotel["305"].id
    readiness = client.get("/api/v1/manager/rooms").json()
    assert readiness["summary"]["awaiting_inspection"] == 1
    assert client.post(f"/api/v1/manager/rooms/{room_id}/inspect", headers=csrf_headers).status_code == 200
    history = client.get(f"/api/v1/tasks/{task['id']}/history").json()["events"]
    assert [e["event"] for e in history] == ["created", "offered", "accepted", "started", "completed"]


def test_role_permissions_are_enforced_by_the_api(
    client: TestClient, csrf_headers, hotel, make_user, login_as
) -> None:
    make_user("desk@example.com", UserRole.RECEPTIONIST)
    make_user("cleaner@example.com", UserRole.HOUSEKEEPING_STAFF)
    make_user("boss@example.com", UserRole.HOUSEKEEPING_MANAGER)
    forbidden = {
        "desk@example.com": ["/api/v1/tasks", "/api/v1/manager/staff", "/api/v1/staff/offers"],
        "cleaner@example.com": ["/api/v1/tasks", "/api/v1/manager/staff", "/api/v1/reception/rooms"],
        "boss@example.com": ["/api/v1/reception/rooms", "/api/v1/staff/offers"],
    }
    for email, paths in forbidden.items():
        login_as(email)
        for path in paths:
            assert client.get(path).status_code == 403, (email, path)
    client.cookies.delete(settings.session_cookie_name)
    assert client.get("/api/v1/tasks").status_code == 401
    assert client.get("/api/v1/guest/requests").status_code == 401


def _add_stay(db: Session, room: Room, phone: str, name: str = "Demo Guest") -> GuestStay:
    stay = GuestStay(
        guest_name=name,
        phone=phone,
        room_id=room.id,
        check_in_at=utcnow() - timedelta(days=1),
        check_out_at=utcnow() + timedelta(days=2),
    )
    db.add(stay)
    db.commit()
    return stay


def _enter_phone(client, csrf, phone: str):
    return client.post("/api/v1/guest/access", headers=csrf, json={"phone": phone})


def test_guest_phone_opens_own_room_and_sees_only_own_requests(
    client: TestClient, db_session: Session, csrf_headers, hotel
) -> None:
    _add_stay(db_session, hotel["305"], "15550100305")
    _add_stay(db_session, hotel["201"], "15550100201", name="Another Guest")

    assert client.get("/api/v1/guest/me").status_code == 401
    entered = _enter_phone(client, csrf_headers, "+1 (555) 010-0305")
    assert entered.status_code == 200, entered.text
    assert entered.json()["room_number"] == "305"
    assert "cleaning" in entered.json()["services"]
    assert client.get("/api/v1/guest/me").json()["room_number"] == "305"

    payload = {"service": "towels", "instructions": "Two bath towels", "client_request_id": "click-abc-123"}
    first = client.post("/api/v1/guest/requests", headers=csrf_headers, json=payload)
    repeat = client.post("/api/v1/guest/requests", headers=csrf_headers, json=payload)
    assert first.status_code == repeat.status_code == 201
    assert first.json()["id"] == repeat.json()["id"]
    assert first.json()["reference"].startswith("HK-")
    assert first.json()["status"] == "Pending Assignment"
    # A room number in the payload is ignored: the room always comes from the matched stay.
    sneaky = client.post(
        "/api/v1/guest/requests",
        headers=csrf_headers,
        json={**payload, "client_request_id": "click-def-456", "room_number": "201"},
    )
    db_session.expire_all()
    assert db_session.get(Task, sneaky.json()["id"]).room_id == hotel["305"].id

    other_guest = TestClient(client.app)
    other_guest.cookies.set(settings.csrf_cookie_name, csrf_headers["X-CSRF-Token"])
    assert _enter_phone(other_guest, csrf_headers, "15550100201").json()["room_number"] == "201"
    assert other_guest.get("/api/v1/guest/requests").json() == []
    assert len(client.get("/api/v1/guest/requests").json()) == 2


def test_unknown_or_ambiguous_numbers_reveal_nothing_and_are_throttled(
    client: TestClient, db_session: Session, csrf_headers, hotel
) -> None:
    _add_stay(db_session, hotel["305"], "15550100999")
    _add_stay(db_session, hotel["306"], "15550100999")
    _add_stay(db_session, hotel["501"], "15550100501")

    unknown = _enter_phone(client, csrf_headers, "15550100000")
    ambiguous = _enter_phone(client, csrf_headers, "15550100999")
    assert unknown.status_code == ambiguous.status_code == 404
    assert unknown.json() == ambiguous.json()
    assert "305" not in ambiguous.text and "306" not in ambiguous.text
    assert client.get("/api/v1/guest/me").status_code == 401

    assert _enter_phone(client, csrf_headers, "12ab").status_code == 422

    for attempt in range(8):
        _enter_phone(client, csrf_headers, f"1555010{attempt:04d}")
    limited = _enter_phone(client, csrf_headers, "15550100501")
    assert limited.status_code == 429


def test_reception_check_in_gives_guest_access_and_check_out_ends_it(
    client: TestClient, db_session: Session, csrf_headers, hotel, make_user, login_as
) -> None:
    make_user("desk@example.com", UserRole.RECEPTIONIST)
    login_as("desk@example.com")
    stay = {"room_number": "306", "guest_name": "  Asha   Rao ", "phone": "+91 98765 43210", "nights": 2}

    checked_in = client.post("/api/v1/reception/check-in", headers=csrf_headers, json=stay)
    assert checked_in.status_code == 201, checked_in.text
    occupancy = checked_in.json()["occupancy"]
    assert occupancy["guest_name"] == "Asha Rao"
    assert occupancy["phone_last4"] == "3210"
    assert "919876543210" not in checked_in.text
    assert checked_in.json()["available"] is False

    again = client.post("/api/v1/reception/check-in", headers=csrf_headers, json=stay)
    assert again.status_code == 409
    same_phone = client.post("/api/v1/reception/check-in", headers=csrf_headers, json={**stay, "room_number": "305"})
    assert same_phone.status_code == 409 and "306" in same_phone.json()["detail"]

    available = client.get("/api/v1/reception/rooms?occupancy=available").json()
    assert "306" not in [room["number"] for room in available]
    occupied = client.get("/api/v1/reception/rooms?occupancy=occupied").json()
    assert [room["number"] for room in occupied] == ["306"]

    guest = TestClient(client.app)
    guest.cookies.set(settings.csrf_cookie_name, csrf_headers["X-CSRF-Token"])
    entered = guest.post("/api/v1/guest/access", headers=csrf_headers, json={"phone": "919876543210"})
    assert entered.status_code == 200 and entered.json()["room_number"] == "306"

    checked_out = client.post("/api/v1/reception/check-out", headers=csrf_headers, json={"room_number": "306"})
    assert checked_out.status_code == 200
    assert checked_out.json()["occupancy"] is None
    assert checked_out.json()["status"] == "cleaning_required"
    assert [t["service"] for t in checked_out.json()["open_requests"]] == ["cleaning"]
    assert guest.get("/api/v1/guest/me").status_code == 401

    not_ready = client.post("/api/v1/reception/check-in", headers=csrf_headers, json={**stay, "phone": "15550101111"})
    assert not_ready.status_code == 409 and "not ready" in not_ready.json()["detail"]
    assert client.post("/api/v1/reception/check-out", headers=csrf_headers, json={"room_number": "306"}).status_code == 409
