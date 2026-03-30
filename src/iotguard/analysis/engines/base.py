"""Protocol definition for pluggable analysis engines.

Any class that implements :class:`AnalysisEngine` can be injected into the
:class:`~iotguard.analysis.service.AnalysisService` pipeline.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from iotguard.analysis.models import AnalysisResult


@runtime_checkable
class AnalysisEngine(Protocol):
    """Structural sub-typing contract for analysis back-ends."""

    async def analyze(
        self,
        command: str,
        device_context: dict[str, Any],
    ) -> AnalysisResult:
        """Evaluate *command* within the given *device_context*.

        Parameters
        ----------
        command:
            The raw IoT command string to analyse.
        device_context:
            Metadata about the target device (``device_id``, ``device_type``,
            ``is_online``, current ``state``, etc.).

        Returns
        -------
        AnalysisResult
            A structured result containing risk level, explanation, and
            optional suggestions.
        """
        ...
