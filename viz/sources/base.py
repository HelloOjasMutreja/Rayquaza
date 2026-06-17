from abc import ABC, abstractmethod
from typing import Iterator
from ..events import StageEvent


class RunSource(ABC):
    """Interface for a run source — yields StageEvents until the run ends."""

    @abstractmethod
    def start(self) -> Iterator[StageEvent]:
        """Yield StageEvents. Blocks until run is complete or stop() is called."""

    @abstractmethod
    def stop(self) -> None:
        """Signal the source to stop yielding and clean up."""
