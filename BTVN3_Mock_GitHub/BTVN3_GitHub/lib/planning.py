# -*- coding: utf-8 -*-
'Schema kế hoạch và điền tham số từ dữ liệu đã quan sát.'
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .config import Constraints


PLAN_STEPS = ["search_flights", "check_seat", "book_seat", "pay", "get_booking"]


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    steps: list[Literal["search_flights", "check_seat", "book_seat", "pay", "get_booking"]] = Field(min_length=1, max_length=12)


def choose_flight(public):
    c = Constraints.model_validate(public["constraints"])
    valid = [f for f in public["candidates"]
             if f["flight_id"] not in public["excluded"] and c.is_ok(f)]
    return min(valid, key=lambda f: (f["price"], f["flight_id"])) if valid else None


def resolve_action(name, public):
    """Deterministic parameter binding for the plan executor, from observed data only."""
    c = public["constraints"]
    if name == "search_flights":
        return {k: c[k] for k in ("origin", "destination", "depart_date")}
    f = choose_flight(public)
    if name == "check_seat":
        return {"flight_id": f["flight_id"]} if f else None
    if name == "book_seat":
        if not f or f["flight_id"] not in public["checked"]:
            return None
        checked = public["checked"][f["flight_id"]]
        return {"flight_id": f["flight_id"], "seat": checked["seats"][0]}
    if name in {"pay", "get_booking"}:
        if not public["booking_code"]:
            return None
        args = {"booking_code": public["booking_code"]}
        if name == "pay":
            args["payment_method"] = "mock_card"
        return args
    return None

