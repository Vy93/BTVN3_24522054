# -*- coding: utf-8 -*-
'Ràng buộc, quyền, ngân sách và danh sách kịch bản.'
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time as clock_time
from pydantic import BaseModel, ConfigDict, Field


class Constraints(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    origin: str = "SGN"
    destination: str = "DAD"
    depart_date: date = date(2026, 10, 7)
    depart_before: clock_time = clock_time(12, 0)
    max_price: int = Field(default=2_000_000, gt=0)
    passenger_id: str = "SV001"
    def is_ok(self, flight: dict) -> bool:
        try:
            return (
                flight["origin"] == self.origin
                and flight["destination"] == self.destination
                and date.fromisoformat(flight["depart_date"]) == self.depart_date
                and clock_time.fromisoformat(flight["depart_time"]) < self.depart_before
                and type(flight["price"]) is int
                and 0 < flight["price"] <= self.max_price
                and flight["currency"] == "VND"
            )
        except (KeyError, ValueError, TypeError):
            return False


@dataclass(frozen=True)
class PermissionPolicy:
    # Trusted configuration, NEVER a tool argument selected by the model.
    auto_limit_vnd: int = 2_000_000
    allow_booking: bool = True
    allow_payment: bool = True
    allow_nonrefundable: bool = False


@dataclass(frozen=True)
class Limits:
    model_calls: int = 24
    tool_calls: int = 24
    seconds: float = 120.0  # cooperative deadline, checked between calls
    repeated_failures: int = 3
    stall_rounds: int = 6
    replans: int = 3


SCENARIOS = ("normal", "sold_out", "over_budget", "need_approval", "timeout")


ARCHITECTURES = ("react", "plan", "hybrid")

