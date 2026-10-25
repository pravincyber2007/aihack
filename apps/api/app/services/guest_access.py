"""Guest access by registered phone number.

A number unlocks room services only when it matches exactly one current stay.
Unknown and ambiguous numbers get the same message and reveal no room details,
and repeated failed lookups from one client are throttled to slow guessing.
"""

import re
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GuestStay
from app.services.assignment import utcnow

FAILED_LOOKUP_WINDOW = timedelta(minutes=15)
FAILED_LOOKUP_LIMIT = 10
_SEPARATORS = re.compile(r"[\s().-]")
# In-memory, per API process: enough to slow guessing on a single server.
_failed_lookups: dict[str, deque[datetime]] = defaultdict(deque)
_failed_lock = threading.Lock()


class GuestAccessError(Exception):
    pass


class GuestLookupLimited(GuestAccessError):
    pass


def normalize_phone(raw: str) -> str:
    """Return digits only, or raise if the input is not a plausible phone number."""
    cleaned = _SEPARATORS.sub("", raw.strip())
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    if not cleaned.isdigit() or not 8 <= len(cleaned) <= 15:
        raise GuestAccessError("Enter a valid phone number, including the country or area code.")
    return cleaned


def current_stays(db: Session, phone: str) -> list[GuestStay]:
    now = utcnow()
    return list(
        db.scalars(
            select(GuestStay).where(
                GuestStay.phone == phone,
                GuestStay.check_in_at <= now,
                GuestStay.check_out_at > now,
            )
        )
    )


def _recent_failures(client_key: str, now: datetime) -> deque[datetime]:
    failures = _failed_lookups[client_key]
    while failures and failures[0] <= now - FAILED_LOOKUP_WINDOW:
        failures.popleft()
    return failures


def find_current_stay(db: Session, phone: str, client_key: str) -> GuestStay:
    now = utcnow()
    with _failed_lock:
        if len(_recent_failures(client_key, now)) >= FAILED_LOOKUP_LIMIT:
            raise GuestLookupLimited("Too many attempts. Please wait a few minutes or contact the front desk.")

    stays = current_stays(db, phone)
    if len(stays) != 1:
        with _failed_lock:
            _recent_failures(client_key, now).append(now)
        # Same message for unknown and ambiguous numbers so neither reveals anything.
        raise GuestAccessError(
            "We couldn't match this number to a current stay. Please check the number or contact the front desk."
        )
    return stays[0]


def reset_lookup_limits() -> None:
    """Clear throttling state (used by tests)."""
    with _failed_lock:
        _failed_lookups.clear()
