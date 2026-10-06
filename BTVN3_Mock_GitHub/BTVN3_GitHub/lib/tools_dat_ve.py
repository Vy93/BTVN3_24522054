# -*- coding: utf-8 -*-
'Backend và năm công cụ đặt vé giả lập. Không giao dịch thật.'
from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Literal
from langchain_core.tools import tool


FLIGHTS = [
    dict(flight_id="VN122", depart_time="08:10", price=1_850_000),
    dict(flight_id="QH118", depart_time="15:40", price=1_640_000),
    dict(flight_id="VJ604", depart_time="10:30", price=2_080_000),
    dict(flight_id="VN134", depart_time="09:20", price=1_950_000),
]


class MockAirline:
    def __init__(self, scenario: str):
        self.scenario = scenario
        self.flights = {
            x["flight_id"]: dict(
                x, origin="SGN", destination="DAD", depart_date="2026-10-07",
                currency="VND", seats=["12A", "12B"], refundable=True,
            ) for x in deepcopy(FLIGHTS)
        }
        if scenario == "over_budget":
            for f in self.flights.values():
                f["price"] += 2_000_000
        self.bookings: dict[str, dict] = {}
        self.hold_keys: dict[tuple, str] = {}
        self.payment_events = 0
    def search(self, origin, destination, depart_date):
        if self.scenario == "timeout":
            return {"status": "error", "error": "TIMEOUT", "retryable": True,
                    "hint": "Có thể thử lại, tối đa theo ngân sách harness."}
        return {"status": "ok", "flights": [
            {k: v for k, v in f.items() if k != "seats"}
            for f in self.flights.values()
            if (f["origin"], f["destination"], f["depart_date"])
            == (origin, destination, depart_date)
        ]}
    def check(self, flight_id):
        f = self.flights.get(flight_id)
        if not f:
            return {"status": "error", "error": "UNKNOWN_FLIGHT", "retryable": False}
        # Inventory can differ from search snapshot: repeatable dynamic scenario.
        if self.scenario == "sold_out" and flight_id == "VN122":
            f["seats"] = []
        if not f["seats"]:
            return {"status": "error", "error": "SOLD_OUT", "retryable": False,
                    "flight_id": flight_id, "hint": "Chọn chuyến khác từ kết quả tìm kiếm."}
        return {"status": "ok", "flight": deepcopy(f)}
    def hold(self, flight_id, seat, passenger_id):
        key = (flight_id, seat, passenger_id)
        if key in self.hold_keys:  # idempotency: retry does not create duplicate booking
            return {"status": "ok", "booking": deepcopy(self.bookings[self.hold_keys[key]])}
        f = self.flights[flight_id]
        if seat not in f["seats"]:
            return {"status": "error", "error": "SOLD_OUT", "retryable": False,
                    "flight_id": flight_id}
        code = f"BK{len(self.bookings) + 1:04d}"
        b = {k: v for k, v in f.items() if k != "seats"}
        b.update(booking_code=code, seat=seat, passenger_id=passenger_id,
                 status="held", paid=False)
        self.bookings[code] = b
        self.hold_keys[key] = code
        f["seats"].remove(seat)
        return {"status": "ok", "booking": deepcopy(b)}
    def pay(self, booking_code):
        b = self.bookings[booking_code]
        if not b["paid"]:  # idempotent payment
            self.payment_events += 1
            b.update(paid=True, status="confirmed")
        return {"status": "ok", "booking_code": booking_code, "paid": True}
    def get(self, booking_code):
        b = self.bookings.get(booking_code)
        return ({"status": "ok", "booking": deepcopy(b)} if b else
                {"status": "error", "error": "UNKNOWN_BOOKING", "retryable": False})


def make_tools(backend: MockAirline, passenger_id: str):
    @tool
    def search_flights(origin: str, destination: str, depart_date: str) -> dict:
        """Find flights; depart_date must be ISO YYYY-MM-DD. Prices include all fees in VND."""
        if date.fromisoformat(depart_date).isoformat() != depart_date:
            raise ValueError("Use YYYY-MM-DD")
        return backend.search(origin, destination, depart_date)
    @tool
    def check_seat(flight_id: str) -> dict:
        """Read current available seats, total price and refund conditions of a searched flight."""
        return backend.check(flight_id)
    @tool
    def book_seat(flight_id: str, seat: str) -> dict:
        """Hold a checked seat. Harness validates constraints and permissions before execution."""
        return backend.hold(flight_id, seat, passenger_id)
    @tool
    def pay(booking_code: str, payment_method: Literal["mock_card"]) -> dict:
        """Pay for an existing held booking with mock_card, subject to trusted permission policy."""
        return backend.pay(booking_code)
    @tool
    def get_booking(booking_code: str) -> dict:
        """Read booking status and paid flag independently; required to verify completion."""
        return backend.get(booking_code)
    return {t.name: t for t in (search_flights, check_seat, book_seat, pay, get_booking)}

