from __future__ import annotations

from typing import Optional

from models import AdvisorProfile, GeneratedMaterial, MatchReport, StudentProfile, Target
from services import make_contact_email


class MaterialDraftAgent:
    """Draft the first candidate while preserving deterministic fallback behavior."""

    name = "MaterialDraftAgent"

    def draft_contact_email(
        self,
        profile: StudentProfile,
        target: Target,
        advisor: Optional[AdvisorProfile],
        match: Optional[MatchReport],
    ) -> GeneratedMaterial:
        material = make_contact_email(profile, target, advisor, match)
        material.title = material.title or "中文套磁邮件草稿"
        return material
