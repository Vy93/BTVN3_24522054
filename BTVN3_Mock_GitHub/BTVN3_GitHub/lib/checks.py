# -*- coding: utf-8 -*-
'Kiểm thử nghiệp vụ và harness kế thừa từ file gốc.'
from __future__ import annotations

from .config import SCENARIOS, ARCHITECTURES, Constraints, PermissionPolicy, Limits
from .runner import run
from .tools_dat_ve import MockAirline
from .harness import BookingHarness


def self_test():
    # Concrete gates: no bypass, no double charge, no false success, termination.
    for arch in ARCHITECTURES:
        for scenario in SCENARIOS:
            r = run(arch, scenario)
            assert r["constraint_violations"] == 0, r
            assert r["unauthorized_payments"] == 0, r
            assert r["goal_achieved"] == r["oracle_goal_achieved"], r
            if not (arch == "plan" and scenario == "sold_out"):
                assert r["expected_outcome_met"], r
        assert run(arch, "normal", limits=Limits(tool_calls=1))["stop_reason"] == "BUDGET_EXCEEDED"
    h = BookingHarness(MockAirline("normal"), Constraints(), PermissionPolicy(), Limits())
    search = dict(origin="SGN", destination="DAD", depart_date="2026-10-07")
    h.execute("search_flights", search)
    h.execute("check_seat", {"flight_id": "QH118"})
    h.execute("book_seat", {"flight_id": "QH118", "seat": "12A"})
    assert h.reason == "CONSTRAINT_DENIED" and not h.backend.bookings
    h = BookingHarness(MockAirline("normal"), Constraints(), PermissionPolicy(allow_booking=False), Limits())
    h.execute("search_flights", search)
    h.execute("check_seat", {"flight_id": "VN122"})
    h.execute("book_seat", {"flight_id": "VN122", "seat": "12A"})
    assert h.reason == "APPROVAL_REQUIRED" and not h.backend.bookings
    b = MockAirline("normal")
    one = b.hold("VN122", "12A", "SV001")
    two = b.hold("VN122", "12A", "SV001")
    assert one == two and len(b.bookings) == 1
    code = one["booking"]["booking_code"]
    b.pay(code); b.pay(code)
    assert b.payment_events == 1
    h = BookingHarness(MockAirline("normal"), Constraints(), PermissionPolicy(), Limits())
    h.execute("pay", {"booking_code": "FAKE", "payment_method": "mock_card"})
    assert not h.is_done() and h.reason == "UNKNOWN_BOOKING"
    print("SELF-TEST PASS: 15 runs + budget/constraints/permission/idempotency/fake-booking checks.")

