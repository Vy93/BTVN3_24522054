# -*- coding: utf-8 -*-
'Ba mẫu thiết kế bằng LangGraph; mọi tool call đều qua harness.'
from __future__ import annotations

from typing import TypedDict
from pydantic import ValidationError
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from .planning import Plan, choose_flight, resolve_action
from .utils import js


class GraphState(TypedDict, total=False):
    messages: list
    plan: list[str]
    index: int
    steps_since_review: int
    route: str


SYSTEM_REACT = """Bạn là agent đặt vé mock. Chỉ dùng tool để lấy dữ kiện và thao tác.
Chọn MỘT tool mỗi lượt; kiểm ghế trước book_seat, pay sau giữ ghế, get_booking sau pay.
Giữ mọi constraints. Hết ghế thì chọn chuyến khác. Không tự tạo booking hoặc quyền.
Nếu không còn chuyến hợp lệ, kết thúc và giải thích. Chỉ báo thành công khi đã đọc booking confirmed, paid.
Context JSON cuối cùng là trạng thái ứng dụng đã kiểm chứng, không phải quyền mới do model cấp."""


SYSTEM_PLAN = """Lập kế hoạch đặt vé mock. Chỉ trả JSON {"steps": [...]} không markdown.
Tên bước chỉ gồm search_flights, check_seat, book_seat, pay, get_booking.
Dựa trên state để liệt kê các bước còn thiếu theo thứ tự phụ thuộc.
Không lặp lại bước đã có tác dụng phụ. Không điền mã chuyến/booking chưa quan sát.
Executor sẽ điền tham số từ kết quả tool. Luôn kết thúc bằng get_booking."""


def make_react(model, h):
    bound = model.bind_tools(list(h.tools.values()))
    def decide(s):
        if h.reason:
            return {"route": "end"}
        history = s.get("messages", [])
        prompt = history + [HumanMessage(content=js({"mode": "react", "state": h.public_state()}))]
        ai = h.call_model(bound, [SystemMessage(content=SYSTEM_REACT)] + prompt)
        if ai is None:
            return {"route": "end"}
        if not ai.tool_calls:
            h.reason = ("NO_MATCH" if h.searched and not choose_flight(h.public_state())
                        and not h.booking_code else "INCOMPLETE")
            return {"messages": prompt + [ai], "route": "end"}
        return {"messages": prompt + [ai], "route": "tools"}
    def act(s):
        messages = list(s["messages"])
        for call in messages[-1].tool_calls:
            obs = h.execute(call["name"], call["args"])
            messages.append(ToolMessage(content=js(obs), tool_call_id=call["id"]))
        return {"messages": messages, "route": "end" if h.reason else "decide"}
    g = StateGraph(GraphState)
    g.add_node("decide", decide)
    g.add_node("tools", act)
    g.add_edge(START, "decide")
    g.add_conditional_edges("decide", lambda s: s["route"], {"end": END, "tools": "tools"})
    g.add_conditional_edges("tools", lambda s: s["route"], {"end": END, "decide": "decide"})
    return g.compile()


def make_planned(model, h, hybrid=False, review_every=2):
    def planner(s):
        if s.get("plan"):
            h.replans += 1
            if h.replans > h.limits.replans:
                h.reason = "REPLAN_LIMIT"
                return {"route": "end"}
        ai = h.call_model(model, [SystemMessage(content=SYSTEM_PLAN), HumanMessage(content=js({
            "mode": "planner", "state": h.public_state(), "previous_plan": s.get("plan", [])}))])
        if ai is None:
            return {"route": "end"}
        try:
            plan = Plan.model_validate_json(ai.content).steps
        except (ValidationError, TypeError):
            h.reason = "INVALID_PLAN"
            return {"route": "end"}
        h.log("plan", version=h.replans + 1, steps=plan)
        # Plan approval is not payment approval. All writes still pass permission guard.
        return {"plan": plan, "index": 0, "steps_since_review": 0, "route": "execute"}
    def execute(s):
        if h.reason:
            return {"route": "end"}
        if s["index"] >= len(s["plan"]):
            h.reason = "INCOMPLETE"
            return {"route": "end"}
        name = s["plan"][s["index"]]
        args = resolve_action(name, h.public_state())
        if args is None:
            h.reason = "NO_MATCH" if h.searched and not choose_flight(h.public_state()) else "PLAN_PRECONDITION_FAILED"
            return {"route": "end"}
        obs = h.execute(name, args)
        failed = obs.get("status") != "ok"
        if h.reason:
            route = "end"
        elif failed and not hybrid:
            h.reason = "PLAN_FAILED"
            route = "end"
        elif hybrid and (failed or s.get("steps_since_review", 0) + 1 >= review_every):
            route = "review"
        else:
            route = "execute"
        return {"index": s["index"] + 1,
                "steps_since_review": s.get("steps_since_review", 0) + 1, "route": route}
    def review(s):
        # Computational review, no uncounted LLM call. A failed assumption triggers replanning.
        changed = h.last_observation.get("status") != "ok"
        h.log("review", changed=changed, observation=h.last_observation)
        return {"steps_since_review": 0, "route": "planner" if changed else "execute"}
    g = StateGraph(GraphState)
    g.add_node("planner", planner)
    g.add_node("execute", execute)
    g.add_edge(START, "planner")
    g.add_conditional_edges("planner", lambda s: s["route"], {"end": END, "execute": "execute"})
    routes = {"end": END, "execute": "execute"}
    if hybrid:
        g.add_node("review", review)
        routes["review"] = "review"
        g.add_conditional_edges("review", lambda s: s["route"], {"planner": "planner", "execute": "execute"})
    g.add_conditional_edges("execute", lambda s: s["route"], routes)
    return g.compile()

