"""
Scheduler Service

Executes time-based schedules and condition-based triggers.
"""

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Dict, Optional, List, Any

from ..core.database import Database
from ..config import settings

logger = logging.getLogger(__name__)


class Scheduler:
    """
    Manages scheduled relay actions and sensor-triggered automation.

    Features:
    - Time-based schedules (daily, weekly, cron-like)
    - Condition-based triggers (sensor thresholds)
    - Cooldown management to prevent rapid switching
    - Integration with device manager for relay control
    """

    def __init__(self, db: Database, device_manager=None):
        self.db = db
        self.device_manager = device_manager
        self._running = False
        self._schedule_task: Optional[asyncio.Task] = None
        self._trigger_task: Optional[asyncio.Task] = None
        self._last_trigger_fire: Dict[str, datetime] = {}  # trigger_id -> last fire time

    def set_device_manager(self, device_manager) -> None:
        """Set the device manager for relay control."""
        self.device_manager = device_manager

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        logger.info("Starting scheduler...")
        self._running = True

        # Start background tasks
        self._schedule_task = asyncio.create_task(self._schedule_loop())
        self._trigger_task = asyncio.create_task(self._trigger_loop())

        logger.info("Scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        if not self._running:
            return

        logger.info("Stopping scheduler...")
        self._running = False

        # Cancel tasks
        for task in [self._schedule_task, self._trigger_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        logger.info("Scheduler stopped")

    async def _schedule_loop(self) -> None:
        """Main schedule checking loop."""
        logger.info("Schedule loop started")

        while self._running:
            try:
                await self._check_schedules()
                # Check every 30 seconds
                await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in schedule loop: {e}")
                await asyncio.sleep(30)

        logger.info("Schedule loop stopped")

    async def _trigger_loop(self) -> None:
        """Main trigger evaluation loop."""
        logger.info("Trigger loop started")

        while self._running:
            try:
                await self._check_triggers()
                # Check triggers every 10 seconds (aligned with sensor polling)
                await asyncio.sleep(10)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in trigger loop: {e}")
                await asyncio.sleep(10)

        logger.info("Trigger loop stopped")

    async def _check_schedules(self) -> None:
        """Check and execute due schedules."""
        schedules = await self.db.get_enabled_schedules()
        now = datetime.now()
        current_time = now.time()
        current_day = now.weekday()  # 0=Monday, 6=Sunday

        for schedule in schedules:
            try:
                action = self._should_execute_schedule(
                    schedule, current_time, current_day
                )

                if action:
                    await self._execute_schedule(schedule, action)

            except Exception as e:
                logger.error(f"Error processing schedule {schedule['id']}: {e}")

    def _should_execute_schedule(
        self,
        schedule: dict,
        current_time: time,
        current_day: int
    ) -> Optional[str]:
        """
        Determine if a schedule should execute now.

        Returns 'on', 'off', or None.
        """
        import json

        # Check days of week (stored as JSON array like "[0,1,2,3,4,5,6]")
        days_str = schedule.get("days_of_week", "[0,1,2,3,4,5,6]")
        try:
            days = json.loads(days_str) if isinstance(days_str, str) else days_str
            if current_day not in days:
                return None
        except (json.JSONDecodeError, TypeError):
            pass  # If parsing fails, assume all days

        # Check time_on
        time_on = schedule.get("time_on")
        if time_on:
            on_time = self._parse_time(time_on)
            if on_time:
                on_dt = datetime.combine(datetime.today(), on_time)
                now_dt = datetime.combine(datetime.today(), current_time)
                diff = abs((now_dt - on_dt).total_seconds())

                if diff <= 30:  # Within 30 seconds of on time
                    return "on"

        # Check time_off
        time_off = schedule.get("time_off")
        if time_off:
            off_time = self._parse_time(time_off)
            if off_time:
                off_dt = datetime.combine(datetime.today(), off_time)
                now_dt = datetime.combine(datetime.today(), current_time)
                diff = abs((now_dt - off_dt).total_seconds())

                if diff <= 30:  # Within 30 seconds of off time
                    return "off"

        return None

    def _parse_time(self, time_str: str) -> Optional[time]:
        """Parse time string to time object."""
        if not time_str:
            return None

        try:
            # Handle different formats
            if isinstance(time_str, time):
                return time_str

            # Try HH:MM:SS
            if len(time_str) == 8:
                parts = time_str.split(":")
                return time(int(parts[0]), int(parts[1]), int(parts[2]))

            # Try HH:MM
            if len(time_str) == 5:
                parts = time_str.split(":")
                return time(int(parts[0]), int(parts[1]))

            return None
        except (ValueError, IndexError):
            return None

    async def _execute_schedule(self, schedule: dict, action: str) -> None:
        """Execute a scheduled action."""
        channel_id = schedule.get("channel_id")

        if not channel_id or not self.device_manager:
            return

        state = action == "on"

        logger.info(
            f"Executing schedule: {schedule.get('name', 'unnamed')} - "
            f"{'ON' if state else 'OFF'}"
        )

        success = await self.device_manager.control_relay(
            channel_id=channel_id,
            state=state,
            source="schedule"
        )

        if success:
            logger.info(f"Schedule executed successfully")
        else:
            logger.error(f"Schedule execution failed")

    async def _check_triggers(self) -> None:
        """Check and execute condition-based triggers."""
        triggers = await self.db.get_enabled_triggers()

        for trigger in triggers:
            try:
                await self._evaluate_trigger(trigger)
            except Exception as e:
                logger.error(f"Error evaluating trigger {trigger['id']}: {e}")

    async def _evaluate_trigger(self, trigger: dict) -> None:
        """Evaluate a single trigger condition."""
        trigger_id = trigger["id"]
        source_channel_id = trigger.get("source_channel_id")
        target_channel_id = trigger.get("target_channel_id")
        operator = trigger.get("operator", "")
        threshold = trigger.get("threshold")
        action = trigger.get("action", "").lower()
        cooldown = trigger.get("cooldown", 300)

        if not all([source_channel_id, target_channel_id, operator, threshold is not None]):
            return

        # Check cooldown
        last_fire = self._last_trigger_fire.get(trigger_id)
        if last_fire:
            elapsed = (datetime.now() - last_fire).total_seconds()
            if elapsed < cooldown:
                return

        # Get latest reading for source channel
        reading = await self.db.get_latest_reading(source_channel_id)
        if not reading:
            return

        value = reading.get("value")
        if value is None:
            return

        # Evaluate condition
        triggered = self._evaluate_condition(value, operator, threshold)

        if triggered:
            logger.info(
                f"Trigger '{trigger.get('name', 'unnamed')}' fired: "
                f"value={value} {operator} {threshold}"
            )

            # Execute action
            if self.device_manager:
                state = action == "on"
                success = await self.device_manager.control_relay(
                    channel_id=target_channel_id,
                    state=state,
                    source="trigger"
                )

                if success:
                    self._last_trigger_fire[trigger_id] = datetime.now()
                    logger.info(f"Trigger action executed: {'ON' if state else 'OFF'}")
                else:
                    logger.error(f"Trigger action failed")

    def _evaluate_condition(
        self,
        value: float,
        operator: str,
        threshold: float
    ) -> bool:
        """Evaluate a trigger condition."""
        operators = {
            ">": lambda v, t: v > t,
            ">=": lambda v, t: v >= t,
            "<": lambda v, t: v < t,
            "<=": lambda v, t: v <= t,
            "==": lambda v, t: abs(v - t) < 0.01,
            "!=": lambda v, t: abs(v - t) >= 0.01,
            # Legacy aliases
            "gt": lambda v, t: v > t,
            "gte": lambda v, t: v >= t,
            "lt": lambda v, t: v < t,
            "lte": lambda v, t: v <= t,
            "eq": lambda v, t: abs(v - t) < 0.01,
        }

        evaluator = operators.get(operator)
        if evaluator:
            return evaluator(value, threshold)

        return False

    async def get_status(self) -> Dict[str, Any]:
        """Get scheduler status."""
        active_schedules = await self.db.get_enabled_schedules()
        active_triggers = await self.db.get_enabled_triggers()

        return {
            "running": self._running,
            "active_schedules": len(active_schedules),
            "active_triggers": len(active_triggers),
            "recent_trigger_fires": {
                tid: ts.isoformat()
                for tid, ts in self._last_trigger_fire.items()
            }
        }
