"""
ds_machine_analyzer/storage/base_storage.py

Abstract storage backend.
All storage implementations (SQLite, PostgreSQL) must inherit from this.

Architecture layer: STORAGE LAYER
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

from core.data_model import CycleLog, CycleStats, EventLogEntry, OEESnapshot


class BaseStorage(ABC):
    """
    Abstract base class for storage backends.
    
    Design: Support both SQLite (laptop) and PostgreSQL (server).
    Same async interface, different implementation.
    """

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to storage backend."""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from storage backend."""
        pass

    @abstractmethod
    async def save_cycle(self, cycle: CycleLog) -> bool:
        """
        Save cycle log to storage.
        
        Args:
            cycle: CycleLog object
            
        Returns:
            True if save successful
        """
        pass

    @abstractmethod
    async def get_cycle(self, machine_id: str, cycle_id: int) -> Optional[CycleLog]:
        """Get cycle by ID."""
        pass

    @abstractmethod
    async def get_cycles(
        self,
        machine_id: str,
        limit: int = 100
    ) -> List[CycleLog]:
        """Get recent cycles for machine."""
        pass

    @abstractmethod
    async def save_step_stats(self, stats: CycleStats) -> bool:
        """Save step statistics."""
        pass

    @abstractmethod
    async def get_step_stats(
        self,
        machine_id: str,
        step_index: int
    ) -> Optional[CycleStats]:
        """Get statistics for a step."""
        pass

    @abstractmethod
    async def get_last_cycle_id(self, machine_id: str) -> int:
        """Return the highest persisted cycle_id for this machine, or 0
        if no cycles have been stored yet.

        Used by `MachineRegistry.start_all()` to seed the adapter's cycle
        counter so it resumes from where the previous process left off
        — preventing UNIQUE(machine_id, cycle_id) collisions on restart.
        """
        pass

    # ------------------------------------------------------------------
    # Pillar 2 — OEE
    # ------------------------------------------------------------------
    @abstractmethod
    async def save_oee_snapshot(self, snapshot: OEESnapshot) -> bool:
        """Persist an OEE rolling-window snapshot."""
        pass

    @abstractmethod
    async def get_recent_oee(
        self, machine_id: str, limit: int = 100
    ) -> List[OEESnapshot]:
        """Return the most-recent OEE snapshots for a machine."""
        pass

    # ------------------------------------------------------------------
    # Pillar 3 — Event Log
    # ------------------------------------------------------------------
    @abstractmethod
    async def save_event(self, event: EventLogEntry) -> EventLogEntry:
        """Persist an event log entry; returns the entry with its id set."""
        pass

    @abstractmethod
    async def get_events(
        self,
        machine_id: str,
        limit: int = 100,
        severity: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[EventLogEntry]:
        """Return the most-recent event log entries (newest first)."""
        pass

    @abstractmethod
    async def acknowledge_event(
        self, event_id: int, *, acknowledged_by: str
    ) -> Optional[EventLogEntry]:
        """Mark an event acknowledged. Returns the updated entry, or None."""
        pass

    # ------------------------------------------------------------------
    # Data Retention
    # ------------------------------------------------------------------
    @abstractmethod
    async def delete_old_data(
        self, cutoff: datetime, *, machine_id: Optional[str] = None
    ) -> int:
        """Delete cycles, OEE snapshots, and events older than *cutoff*.

        Returns the total number of rows deleted across all tables.
        When *machine_id* is given, only that machine's data is purged.
        """
        pass
