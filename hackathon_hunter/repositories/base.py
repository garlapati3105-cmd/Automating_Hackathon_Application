"""
Abstract repository interface for hackathon storage.

Any storage backend (SQLite, PostgreSQL, JSON file, etc.) must implement
this interface. Business logic only depends on this ABC — never on a
concrete implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from hackathon_hunter.models.hackathon import Hackathon


class AbstractHackathonRepository(ABC):
    """Interface for hackathon persistence."""

    @abstractmethod
    def initialize(self) -> None:
        """
        Prepare the storage backend (create tables, directories, etc.).
        Called once on startup before any reads or writes.
        """
        ...

    @abstractmethod
    def exists(self, url: str) -> bool:
        """
        Return True if a hackathon with the given URL already exists in
        storage. Used for fast duplicate checking before an insert attempt.

        Args:
            url: The canonical URL of the hackathon.
        """
        ...

    @abstractmethod
    def add(self, hackathon: Hackathon) -> bool:
        """
        Persist a hackathon to storage.

        Returns:
            True  — the hackathon was new and was successfully inserted.
            False — a hackathon with the same URL already existed; skipped.

        Raises:
            RuntimeError: On any unrecoverable storage error.
        """
        ...

    @abstractmethod
    def list_all(self) -> list[Hackathon]:
        """
        Return all stored hackathons, ordered by first_seen descending.
        """
        ...
