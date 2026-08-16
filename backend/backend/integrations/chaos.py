from __future__ import annotations

from dataclasses import dataclass, field


class ChaosInjectedError(RuntimeError):
    """Raised by ChaosState.maybe_fail() to simulate an external-dependency
    timeout/outage at a real point in the call graph (a specific agent's
    call to a specific tool). AgentSupport.call_tool catches this, emits
    CHAOS_FAILURE_INJECTED, retries the same tool call once, and emits
    CHAOS_RETRY_SUCCEEDED - a real (if simulated) failure-and-recovery path,
    not just a log line claiming one happened."""


@dataclass
class ChaosState:
    """Toggleable at runtime via POST /api/chaos/enable|disable - no server
    restart needed to demo it. When enabled, the FIRST call to any given
    checkpoint (one per agent+tool+review) fails; every call after that
    succeeds - deterministic, not randomized, so the failure-then-recovery
    sequence is reproducible on every demo run rather than a coin flip that
    might not fire. Disabling clears the fired-checkpoint set so re-enabling
    starts a fresh failure cycle."""

    enabled: bool = False
    _fired: set[str] = field(default_factory=set)

    def enable(self) -> None:
        self.enabled = True
        self._fired.clear()

    def disable(self) -> None:
        self.enabled = False
        self._fired.clear()

    def maybe_fail(self, checkpoint: str) -> None:
        if not self.enabled or checkpoint in self._fired:
            return
        self._fired.add(checkpoint)
        raise ChaosInjectedError(f"[CHAOS] simulated failure at checkpoint '{checkpoint}'")
