"""Catalog load + SKU model."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ach.paths import DEFAULT_CATALOG


class Sku(BaseModel):
    id: str
    vendor: str
    name: str
    kind: Literal["physical", "virtual", "service"]
    family: str
    deployment: Literal["on_prem", "virtual", "hybrid", "na"]
    perf: Literal["entry", "standard", "pro", "na"]
    spare: Literal["ready", "no", "na"]
    os: Literal["windows", "chromeos", "browser", "na"]
    license: Literal["perpetual", "subscription", "na"]
    vcpu: int | None = None
    ram_gb: int | None = None
    certs: list[str] = Field(default_factory=list)
    sla: Literal["8x5", "24x7", "na"] = "na"
    compatible_with: list[str] = Field(default_factory=list)
    ports: int | None = None
    form_factor: str | None = None
    marketing_blurb: str = ""

    @property
    def is_appliance(self) -> bool:
        return self.kind in ("physical", "virtual")


class Catalog(BaseModel):
    version: str
    skus: list[Sku]

    def by_id(self) -> dict[str, Sku]:
        return {s.id: s for s in self.skus}

    def get(self, sku_id: str) -> Sku:
        return self.by_id()[sku_id]


def load_catalog(path: Path | str | None = None) -> Catalog:
    p = Path(path) if path else DEFAULT_CATALOG
    data = json.loads(p.read_text(encoding="utf-8"))
    return Catalog.model_validate(data)
