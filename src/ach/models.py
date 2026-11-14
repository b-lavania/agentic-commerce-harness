"""Shared pydantic models for checklist, handoff, scenarios."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class QuoteLine(BaseModel):
    sku_id: str
    qty: int = 1
    line_type: Literal["setup", "recurring", "usage"]


class Checklist(BaseModel):
    intent: str | None = None
    facets: dict[str, Any] = Field(default_factory=dict)
    compared_ids: list[str] = Field(default_factory=list)
    selected_appliances: list[str] = Field(default_factory=list)
    shortlist: list[str] = Field(default_factory=list)
    committed: list[str] = Field(default_factory=list)
    quote_lines: list[QuoteLine] = Field(default_factory=list)
    invoice_id: str | None = None
    invoice_state: str | None = None
    attached_addons: list[str] = Field(default_factory=list)
    listed_addon_ids: list[str] = Field(default_factory=list)
    milestones: set[str] = Field(default_factory=set)
    forbidden_hits: list[str] = Field(default_factory=list)


class Handoff(BaseModel):
    shortlist_ids: list[str]
    quote_lines: list[QuoteLine]
    invoice_id: str | None = None
    invoice_state: str | None = None
    checkout_session_id: str | None = None
    currency: str | None = None
    counter_scenario_id: str | None = None


class Mandate(BaseModel):
    max_recurring_cents_per_month: int | None = None
    allowed_line_types: list[str] = Field(default_factory=lambda: ["setup", "recurring"])


class ListingOverlay(BaseModel):
    sku_id: str
    sponsored: bool = False
    platform_pick: bool = False


class BuyerTask(BaseModel):
    intent: str = ""
    constraints: dict[str, Any] = Field(default_factory=dict)
    preferences: list[dict[str, Any]] = Field(default_factory=list)
    result_order: list[str] = Field(default_factory=list)
    listing_overlays: list[ListingOverlay] = Field(default_factory=list)
    must_consider_addon: str | None = None
    mandate: Mandate | None = None


class ScenarioStepExpect(BaseModel):
    ok: bool | None = None
    error: str | None = None
    forbidden: bool | None = None
    oracle_pass: bool | None = None
    recon_blocked: bool | None = None


class ScenarioStep(BaseModel):
    action: str
    body: dict[str, Any] = Field(default_factory=dict)
    expect: ScenarioStepExpect = Field(default_factory=ScenarioStepExpect)


class ScenarioExpect(BaseModel):
    shortlist_passes_oracle: bool | None = None
    milestones: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    invoice_state: str | None = None
    recon_blocked: bool | None = None
    must_not_send: bool | None = None
    must_refuse_sent_rewrite: bool | None = None
    forbidden_actions: list[str] = Field(default_factory=list)


class Scenario(BaseModel):
    id: str
    horizon: Literal["h1", "h2"]
    description: str = ""
    catalog: str | None = None
    pricebook: str | None = None
    fixture: str | None = None
    max_macro_steps: int = 40
    task: BuyerTask | None = None
    steps: list[ScenarioStep] = Field(default_factory=list)
    expect: ScenarioExpect = Field(default_factory=ScenarioExpect)


class TrajectoryRow(BaseModel):
    scenario_id: str
    step: int
    action: str
    observation_hash: str
    milestone_hits: list[str]
    forbidden: list[str]
    ok: bool
    detail: dict[str, Any] = Field(default_factory=dict)
    horizon: str | None = None
    delegate: dict[str, Any] | None = None
    mandate_violation: str | None = None
