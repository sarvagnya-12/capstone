from __future__ import annotations

import re
from hashlib import sha1

from catalog_builder.models import NormalizedProduct, RawProduct
from catalog_builder.taxonomy_loader import Taxonomy


class ProductNormalizer:
    def __init__(self, taxonomy: Taxonomy) -> None:
        self.taxonomy = taxonomy

    def normalize(self, product: RawProduct) -> NormalizedProduct:
        brand = self.taxonomy.canonical_brand(product.brand)
        category = self.taxonomy.canonical_category(product.category or product.subcategory)
        gender = self.taxonomy.canonical_gender(product.gender or product.subcategory)
        primary_color, secondary_color = self._colors(product)
        material = self.taxonomy.canonical_material(product.material or product.name)
        model = self._model_name(product.name, brand)
        fingerprint = self.fingerprint(brand, model, category, gender)

        return NormalizedProduct(
            product_id=None,
            brand=brand,
            model=model,
            category=category,
            subcategory=self._title(product.subcategory),
            gender=gender,
            retail_price=product.retail_price,
            release_year=product.release_year,
            primary_color=primary_color,
            secondary_color=secondary_color,
            material=material,
            source_url=product.source_url,
            source=product.source,
            source_product_id=product.source_product_id,
            confidence=1.0,
            status="normalized",
            fingerprint=fingerprint,
            raw_name=product.name,
            description=product.description,
        )

    def fingerprint(self, brand: str | None, model: str | None, category: str | None, gender: str | None) -> str:
        readable = "|".join((brand or "", model or "", category or "", gender or "")).lower()
        digest = sha1(readable.encode("utf-8")).hexdigest()[:12]
        return f"{self._slug(readable)}-{digest}"

    def _model_name(self, name: str | None, brand: str | None) -> str | None:
        if not name:
            return None
        text = self.taxonomy.normalize_model_terms(name)
        text = re.sub(r"\b(men|women)'?s\b", " ", text, flags=re.IGNORECASE)
        if brand:
            text = re.sub(rf"\b{re.escape(brand)}\b", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"[^A-Za-z0-9\s-]", " ", text)
        tokens = []
        for token in re.split(r"[\s-]+", text):
            clean = token.strip().lower()
            if not clean or clean in self.taxonomy.product_stopwords:
                continue
            tokens.append(clean)
        if not tokens:
            return None
        return " ".join(tokens).title()

    def _colors(self, product: RawProduct) -> tuple[str | None, str | None]:
        color_parts = self._split_colors(product.primary_color)
        primary = self.taxonomy.canonical_color(color_parts[0] if color_parts else product.primary_color)
        secondary = self.taxonomy.canonical_color(product.secondary_color)
        if secondary is None and len(color_parts) > 1:
            secondary = self.taxonomy.canonical_color(color_parts[1])
        if primary is None and product.name:
            primary = self.taxonomy.canonical_color(product.name)
        if secondary == primary:
            secondary = None
        return primary, secondary

    @staticmethod
    def _split_colors(value: str | None) -> list[str]:
        if not value:
            return []
        return [part.strip() for part in re.split(r"[/,&+]", value) if part.strip()]

    @staticmethod
    def _title(value: str | None) -> str | None:
        if not value:
            return None
        return re.sub(r"\s+", " ", value).strip().title()

    @staticmethod
    def _slug(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "unknown"
