# -*- coding: utf-8 -*-
'Model giả tương thích LangChain để kiểm thử offline; không phải LLM.'
from __future__ import annotations

import json
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from .planning import PLAN_STEPS, choose_flight, resolve_action
from .utils import js


class ModelGia(BaseChatModel):
    @property
    def _llm_type(self):
        return "se373-flight-mock"
    def bind_tools(self, tools, **kwargs):
        return self
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        payload = json.loads(messages[-1].content)
        p = payload["state"]
        if payload["mode"] == "planner":
            if p["booking_code"]:
                steps = ["get_booking"] if p["paid"] else ["pay", "get_booking"]
            elif p["searched"]:
                steps = PLAN_STEPS[1:]
            else:
                steps = PLAN_STEPS
            ai = AIMessage(content=js({"steps": steps}))
        else:
            if p["booking_code"]:
                name = "get_booking" if p["paid"] else "pay"
            elif not p["searched"]:
                name = "search_flights"
            else:
                f = choose_flight(p)
                name = "book_seat" if f and f["flight_id"] in p["checked"] else "check_seat"
            args = resolve_action(name, p)
            if args is None:
                ai = AIMessage(content="Không tìm thấy chuyến đáp ứng ràng buộc từ dữ liệu đã có.")
            else:
                cid = f"call_{sum(isinstance(m, AIMessage) for m in messages) + 1}"
                ai = AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid}])
        return ChatResult(generations=[ChatGeneration(message=ai)])

