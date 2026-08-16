from __future__ import annotations

import json
from pathlib import Path


class ProductIdRegistry:
    def __init__(self, registry_path: Path, category_code: str) -> None:
        self.registry_path = registry_path
        self.category_code = category_code
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def get_or_create(self, fingerprint: str) -> str:
        products = self._data.setdefault("products", {})
        if fingerprint in products:
            return str(products[fingerprint])
        next_number = int(self._data.get("next_number", 1))
        product_id = f"DRY-{self.category_code}-{next_number:06d}"
        products[fingerprint] = product_id
        self._data["next_number"] = next_number + 1
        self.save()
        return product_id

    def save(self) -> None:
        self.registry_path.write_text(json.dumps(self._data, indent=2, sort_keys=True), encoding="utf-8")

    def _load(self) -> dict:
        if self.registry_path.exists():
            return json.loads(self.registry_path.read_text(encoding="utf-8"))
        return {"next_number": 1, "products": {}}

