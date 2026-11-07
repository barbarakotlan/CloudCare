"""Epic MyChart integration (SMART on FHIR standalone launch, patient-facing).

Setup and sandbox testing: docs/epic-mychart.md.
"""

from app.epic.router import router

__all__ = ["router"]
