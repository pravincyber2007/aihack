"""Load clearly labelled DEMO rooms and guest stays.

The hotel has no reservation system connected yet, so this creates sample data
for demonstrating the guest and housekeeping flows. Run from apps/api:

    python -m app.demo_seed
"""

from datetime import timedelta

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import GuestStay, Room, RoomStatus
from app.services.assignment import get_settings, utcnow

FLOORS = range(1, 6)
ROOMS_PER_FLOOR = 10
# (phone digits, room number). The last number deliberately has two stays to
# demonstrate that ambiguous matches never reveal a room.
DEMO_STAYS = [
    ("15550100305", "305"),
    ("15550100208", "208"),
    ("15550100999", "401"),
    ("15550100999", "402"),
]


def seed() -> None:
    with SessionLocal.begin() as db:
        existing = set(db.scalars(select(Room.number)))
        for floor in FLOORS:
            for index in range(1, ROOMS_PER_FLOOR + 1):
                number = f"{floor}{index:02d}"
                if number not in existing:
                    db.add(Room(number=number, floor=floor, status=RoomStatus.READY))
        db.flush()

        rooms = {room.number: room for room in db.scalars(select(Room))}
        now = utcnow()
        for phone, number in DEMO_STAYS:
            room = rooms[number]
            current = db.scalar(
                select(GuestStay).where(GuestStay.phone == phone, GuestStay.room_id == room.id)
            )
            if current is None:
                current = GuestStay(guest_name="DEMO guest", phone=phone, room_id=room.id)
                db.add(current)
            # Refresh dates so demo stays are current whenever the script is run.
            current.check_in_at = now - timedelta(days=1)
            current.check_out_at = now + timedelta(days=7)
        get_settings(db)

    print(f"Demo data ready: {len(FLOORS) * ROOMS_PER_FLOOR} rooms on floors 1-5.")
    print("DEMO guest phone numbers (current stays):")
    print("  +1 555 010 0305 -> room 305")
    print("  +1 555 010 0208 -> room 208")
    print("  +1 555 010 0999 -> two stays (shows the 'cannot verify' path)")


if __name__ == "__main__":
    seed()
