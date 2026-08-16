from __future__ import annotations

from pathlib import Path

from review_builder.models import RawReview
from shared.collectors import BaseCollector


class BaseReviewCollector(BaseCollector):
    service_name = "review_builder"
    auto_register = False
    source_name: str

    def collect(self, input_path: Path) -> list[RawReview]:
        """Read source review data and return raw reviews."""
        raise NotImplementedError
