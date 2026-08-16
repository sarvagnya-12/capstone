from __future__ import annotations

import json
import re
from pathlib import Path


class Taxonomy:
    def __init__(self, taxonomy_dir: Path) -> None:
        self.taxonomy_dir = taxonomy_dir
        self.brands = self._load("brands.json")
        self.categories = self._load("categories.json")
        self.colors = self._load("colors.json")
        self.materials = self._load("materials.json")
        self.stopwords = self._load("stopwords.json")
        self.synonyms = self._load("synonyms.json")

    def canonical_brand(self, value: str | None) -> str | None:
        return self._canonical(value, self.brands.get("canonical", {}))

    def canonical_category(self, value: str | None) -> str | None:
        if value is None or not str(value).strip():
            return None
        category = self._canonical(value, self.categories.get("canonical", {}))
        return category or self.categories.get("default_category")

    def canonical_color(self, value: str | None) -> str | None:
        return self._canonical(value, self.colors.get("canonical", {}))

    def canonical_material(self, value: str | None) -> str | None:
        return self._canonical(value, self.materials.get("canonical", {}))

    def canonical_gender(self, value: str | None) -> str | None:
        return self._canonical(value, self.synonyms.get("gender", {}))

    def normalize_model_terms(self, value: str) -> str:
        normalized = value
        for canonical, aliases in self.synonyms.get("model_terms", {}).items():
            for alias in aliases:
                normalized = re.sub(rf"\b{re.escape(alias)}\b", canonical, normalized, flags=re.IGNORECASE)
        return normalized

    @property
    def product_stopwords(self) -> set[str]:
        return {word.lower() for word in self.stopwords.get("product_name", [])}

    def _load(self, name: str) -> dict:
        return json.loads((self.taxonomy_dir / name).read_text(encoding="utf-8"))

    @staticmethod
    def _canonical(value: str | None, mapping: dict[str, list[str]]) -> str | None:
        if value is None:
            return None
        clean = str(value).strip().lower()
        if not clean:
            return None
        for canonical, aliases in mapping.items():
            choices = {canonical.lower(), *(alias.lower() for alias in aliases)}
            if clean in choices:
                return canonical
        for canonical, aliases in mapping.items():
            choices = [canonical.lower(), *(alias.lower() for alias in aliases)]
            if any(re.search(rf"\b{re.escape(choice)}\b", clean) for choice in choices):
                return canonical
        return value.strip().title()
