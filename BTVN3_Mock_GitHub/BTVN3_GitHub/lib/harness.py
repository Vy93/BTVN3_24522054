# -*- coding: utf-8 -*-
'Kiểm tham số, ràng buộc, quyền, hoàn thành, ngân sách và bàn giao.'
from __future__ import annotations

import time
from collections import deque
from copy import deepcopy
from pydantic import ValidationError
from .config import Constraints, PermissionPolicy, Limits
from .tools_dat_ve import make_tools
from .utils import js


class BookingHarness:
    def __init__(self, backend, constraints, policy, limits):
        self.backend, self.constraints, self.policy, self.limits = backend, constraints, policy, limits
        self.tools = make_tools(backend, constraints.passenger_id)
        self.started = time.perf_counter()
        self.trace: list[dict] = []
        self.model_calls = self.tool_calls = self.blocked_calls = 0
        self.input_tokens = self.output_tokens = 0
        self.usage_records = 0
        self.reason: str | None = None
        self.candidates: list[dict] = []
        self.searched = False
        self.checked: dict[str, dict] = {}
        self.excluded: set[str] = set()
        self.booking_code: str | None = None
        self.verified: dict | None = None
        self.last_observation: dict = {}
        self.failures = deque(maxlen=6)
        self.stall = 0
        self.last_progress = None
        self.replans = 0
    def log(self, event, **data):
        self.trace.append({"event": event, **deepcopy(data)})
    def public_state(self):
        return {
            "constraints": self.constraints.model_dump(mode="json"),
            "searched": self.searched, "candidates": self.candidates,
            "checked": self.checked, "excluded": sorted(self.excluded),
            "booking_code": self.booking_code,
            "paid": bool(self.booking_code and self.backend.bookings[self.booking_code]["paid"]),
            "last_observation": self.last_observation,
        }
    def is_done(self):
        b = self.verified
        return bool(b and b.get("status") == "confirmed" and b.get("paid") is True
                    and b.get("booking_code") == self.booking_code
                    and b.get("passenger_id") == self.constraints.passenger_id
                    and self.constraints.is_ok(b))
    def budget_available(self, kind):
        # Hard preflight guard avoids starting another call beyond the limit.
        exceeded = (time.perf_counter() - self.started >= self.limits.seconds
                    or (kind == "model" and self.model_calls >= self.limits.model_calls)
                    or (kind == "tool" and self.tool_calls >= self.limits.tool_calls))
        if exceeded:
            self.reason = "BUDGET_EXCEEDED"
        return not exceeded
    def call_model(self, model, messages):
        if not self.budget_available("model"):
            return None
        self.model_calls += 1
        response = model.invoke(messages)
        usage = getattr(response, "usage_metadata", None)
        if usage:
            self.usage_records += 1
            self.input_tokens += usage.get("input_tokens", 0)
            self.output_tokens += usage.get("output_tokens", 0)
        self.log("model", content=response.content,
                 tool_calls=getattr(response, "tool_calls", []))
        return response
    def guard(self, name, args):
        if name == "check_seat" and args["flight_id"] not in {f["flight_id"] for f in self.candidates}:
            return "UNSOURCED_FLIGHT"
        if name == "book_seat":
            fid = args["flight_id"]
            observed = self.checked.get(fid)
            current = self.backend.flights.get(fid)
            if not observed or not current:
                return "CHECK_SEAT_REQUIRED"
            if not self.constraints.is_ok(current):
                return "CONSTRAINT_DENIED"
            if current["price"] != observed["price"]:
                return "PRICE_CHANGED"
            if not self.policy.allow_booking:
                return "APPROVAL_REQUIRED"
            if (current["price"] > self.policy.auto_limit_vnd
                or (not current["refundable"] and not self.policy.allow_nonrefundable)):
                return "APPROVAL_REQUIRED"
        if name in {"pay", "get_booking"}:
            code = args["booking_code"]
            if code != self.booking_code or code not in self.backend.bookings:
                return "UNKNOWN_BOOKING"
            b = self.backend.bookings[code]
            if b["passenger_id"] != self.constraints.passenger_id:
                return "PERMISSION_DENIED"
            if name == "pay":
                if not self.constraints.is_ok(b):
                    return "CONSTRAINT_DENIED"
                if (not self.policy.allow_payment or b["price"] > self.policy.auto_limit_vnd
                    or (not b["refundable"] and not self.policy.allow_nonrefundable)):
                    return "APPROVAL_REQUIRED"
        return None
    def execute(self, name, args):
        if self.reason:
            return {"status": "stopped", "reason": self.reason}
        self.log("proposed", tool=name, args=args)
        if not self.budget_available("tool"):
            return {"status": "stopped", "reason": self.reason}
        try:
            if name not in self.tools:
                raise ValueError("Unknown tool")
            # Extra arguments are rejected, including any model-invented approval flag.
            schema = self.tools[name].get_input_schema()
            if set(args) - set(schema.model_fields):
                raise ValueError("Unexpected argument")
            parsed = schema.model_validate(args).model_dump()
            denied = self.guard(name, parsed)
        except (ValidationError, ValueError, TypeError, KeyError) as exc:
            denied = "INVALID_TOOL_OR_ARGS"
            self.log("validation_error", detail=str(exc))
        if denied:
            self.blocked_calls += 1
            self.reason = denied
            obs = {"status": "denied", "error": denied}
            self.last_observation = obs
            self.log("blocked", tool=name, args=args, observation=obs)
            return obs
        self.tool_calls += 1
        try:
            obs = self.tools[name].invoke(parsed)
        except Exception as exc:
            obs = {"status": "error", "error": "TOOL_EXCEPTION", "retryable": False,
                   "detail": f"{type(exc).__name__}: {exc}"}
        self.last_observation = obs
        self.log("executed", tool=name, args=parsed, observation=obs)
        if obs.get("status") == "ok":
            if name == "search_flights":
                self.searched = True
                self.candidates = obs["flights"]
            elif name == "check_seat":
                self.checked[parsed["flight_id"]] = obs["flight"]
            elif name == "book_seat":
                self.booking_code = obs["booking"]["booking_code"]
            elif name == "get_booking":
                self.verified = obs["booking"]
        elif obs.get("error") == "SOLD_OUT":
            self.excluded.add(parsed["flight_id"])
            self.checked.pop(parsed["flight_id"], None)
        self.after_observation(name, parsed, obs)
        return obs
    def after_observation(self, name, args, obs):
        if self.is_done():
            self.reason = "SUCCESS"
            return
        # Bounded retries: only repeated unsuccessful actions count as useless loops.
        # Successful get_booking polling is governed by progress and total budgets.
        fp = js([name, args])
        self.failures.append(fp if obs.get("status") != "ok" else None)
        if self.failures.count(fp) >= self.limits.repeated_failures:
            self.reason = "LOOP_DETECTED"
            return
        progress = (self.searched, len(self.checked) + len(self.excluded),
                    bool(self.booking_code), self.public_state()["paid"], self.is_done())
        self.stall = self.stall + 1 if progress == self.last_progress else 0
        self.last_progress = progress
        if self.stall >= self.limits.stall_rounds:
            self.reason = "STALL_DETECTED"
            return
        if (self.tool_calls >= self.limits.tool_calls
            or time.perf_counter() - self.started >= self.limits.seconds):
            self.reason = "BUDGET_EXCEEDED"
    def finish(self):
        if self.is_done():
            self.reason = "SUCCESS"
        if self.reason is None:
            self.reason = "INCOMPLETE"
        b = deepcopy(self.backend.bookings.get(self.booking_code))
        handoff = None
        if self.reason != "SUCCESS":
            question = ("Bạn có cho phép thao tác bị chặn với booking/chuyến và giá trong trace không?"
                        if self.reason == "APPROVAL_REQUIRED" else
                        "Bạn muốn đổi ràng buộc, thử lại dịch vụ, hay chuyển người hỗ trợ?")
            handoff = {"stop_reason": self.reason,
                       "da_thu": [x for x in self.trace if x["event"] in {"executed", "blocked"}],
                       "trang_thai": {"booking": b, "paid": bool(b and b["paid"]),
                                      "last_observation": self.last_observation},
                       "cau_hoi_cho_nguoi": question}
        return {"stop_reason": self.reason, "goal_achieved": self.is_done(),
                "booking": b, "handoff": handoff, "model_calls": self.model_calls,
                "tool_calls": self.tool_calls, "blocked_calls": self.blocked_calls,
                "replans": self.replans, "elapsed_seconds": round(time.perf_counter() - self.started, 6),
                "input_tokens": self.input_tokens if self.usage_records else None,
                "output_tokens": self.output_tokens if self.usage_records else None,
                "trace": self.trace}

