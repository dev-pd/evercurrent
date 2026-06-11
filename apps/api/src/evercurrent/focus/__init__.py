"""Focus model: a per-member relevance profile combining role, project phase,
and learned behaviour (feedback). Powers the "Your Focus" panel + feeds the
digest judge. Pure computation in `compute`, wire shapes in `schemas`.
"""

from evercurrent.focus.compute import compute_focus
from evercurrent.focus.schemas import FocusTopic

__all__ = ["FocusTopic", "compute_focus"]
