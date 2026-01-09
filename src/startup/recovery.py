"""
Startup Recovery System

Restores relay states and applies schedules after power outage or restart.
"""

import logging
from datetime import datetime, time
from typing import Optional

from ..core.database import Database
from ..config import settings

logger = logging.getLogger(__name__)


async def run_startup_recovery(db: Database) -> None:
    """
    Main startup recovery routine.

    This function:
    1. Restores relay states to their last known values
    2. Applies any schedules that should be active now
    3. Logs recovery actions for debugging

    Args:
        db: Database instance
    """
    logger.info("Starting recovery process...")

    # Step 1: Restore relay states
    if settings.recover_relay_states:
        await restore_relay_states(db)

    # Step 2: Apply active schedules
    await apply_active_schedules(db)

    logger.info("Recovery process complete")


async def restore_relay_states(db: Database) -> None:
    """
    Restore relays to their last known state.

    Reads the most recent state for each relay from the database
    and queues commands to restore those states.
    """
    logger.info("Restoring relay states...")

    # Get all relay channels
    relay_channels = await db.get_relay_channels()

    restored_count = 0
    for channel in relay_channels:
        channel_id = channel["id"]

        # Get last known state
        last_state = await db.get_last_relay_state(channel_id)

        if last_state:
            state = bool(last_state["state"])
            source = last_state["source"]

            logger.info(
                f"Relay {channel['name']} ({channel_id}): "
                f"restoring to {'ON' if state else 'OFF'} "
                f"(last set by {source})"
            )

            # Record the recovery state change
            await db.add_relay_state(channel_id, state, "recovery")
            restored_count += 1
        else:
            logger.debug(f"Relay {channel['name']}: no previous state found")

    logger.info(f"Restored {restored_count} relay states")


async def apply_active_schedules(db: Database) -> None:
    """
    Apply schedules that should currently be active.

    Checks all enabled schedules and applies any that:
    - Match the current day of week
    - Have a time_on before now and time_off after now
    """
    logger.info("Applying active schedules...")

    now = datetime.now()
    current_day = now.strftime("%A").lower()  # monday, tuesday, etc.
    current_time = now.time()

    # Get all enabled schedules
    schedules = await db.get_enabled_schedules()

    applied_count = 0
    for schedule in schedules:
        # Check if schedule applies to current day
        days = schedule["days_of_week"].split(",") if schedule["days_of_week"] else []
        if current_day not in [d.strip().lower() for d in days]:
            continue

        # Parse times
        time_on = parse_time(schedule["time_on"])
        time_off = parse_time(schedule["time_off"])

        if not time_on or not time_off:
            logger.warning(f"Schedule {schedule['id']}: invalid time format")
            continue

        # Determine if relay should be ON right now
        should_be_on = False

        if time_on < time_off:
            # Normal case: e.g., 08:00 to 18:00
            should_be_on = time_on <= current_time < time_off
        else:
            # Overnight case: e.g., 22:00 to 06:00
            should_be_on = current_time >= time_on or current_time < time_off

        if should_be_on:
            channel_id = schedule["channel_id"]
            logger.info(
                f"Schedule {schedule['name']}: activating relay {channel_id} "
                f"({time_on} - {time_off})"
            )
            await db.add_relay_state(channel_id, True, "schedule")
            applied_count += 1

    logger.info(f"Applied {applied_count} active schedules")


def parse_time(time_str: str) -> Optional[time]:
    """Parse a time string into a time object."""
    if not time_str:
        return None

    try:
        # Try HH:MM format
        parts = time_str.split(":")
        if len(parts) >= 2:
            return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        pass

    return None


async def check_schedule_overlap(
    db: Database,
    channel_id: str,
    days: str,
    time_on: str,
    time_off: str,
    exclude_schedule_id: Optional[str] = None
) -> bool:
    """
    Check if a schedule would overlap with existing schedules.

    Args:
        db: Database instance
        channel_id: The relay channel ID
        days: Comma-separated days of week
        time_on: Start time (HH:MM)
        time_off: End time (HH:MM)
        exclude_schedule_id: Schedule ID to exclude from check (for updates)

    Returns:
        True if there's an overlap, False otherwise
    """
    existing = await db.get_all_schedules()

    new_days = set(d.strip().lower() for d in days.split(","))
    new_on = parse_time(time_on)
    new_off = parse_time(time_off)

    if not new_on or not new_off:
        return False

    for schedule in existing:
        # Skip if different channel
        if schedule["channel_id"] != channel_id:
            continue

        # Skip if this is the same schedule (for updates)
        if exclude_schedule_id and schedule["id"] == exclude_schedule_id:
            continue

        # Skip if disabled
        if not schedule["enabled"]:
            continue

        # Check day overlap
        existing_days = set(
            d.strip().lower()
            for d in (schedule["days_of_week"] or "").split(",")
        )
        if not new_days.intersection(existing_days):
            continue

        # Check time overlap
        existing_on = parse_time(schedule["time_on"])
        existing_off = parse_time(schedule["time_off"])

        if not existing_on or not existing_off:
            continue

        if times_overlap(new_on, new_off, existing_on, existing_off):
            return True

    return False


def times_overlap(
    a_start: time,
    a_end: time,
    b_start: time,
    b_end: time
) -> bool:
    """Check if two time ranges overlap."""
    # Convert to minutes for easier comparison
    def to_minutes(t: time) -> int:
        return t.hour * 60 + t.minute

    a1, a2 = to_minutes(a_start), to_minutes(a_end)
    b1, b2 = to_minutes(b_start), to_minutes(b_end)

    # Handle overnight ranges
    if a1 > a2:
        a2 += 24 * 60
    if b1 > b2:
        b2 += 24 * 60

    # Check overlap
    return not (a2 <= b1 or b2 <= a1)
