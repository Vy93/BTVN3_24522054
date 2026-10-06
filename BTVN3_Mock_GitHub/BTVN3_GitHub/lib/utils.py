# -*- coding: utf-8 -*-
'Tiện ích chuyển dữ liệu sang JSON.'
from __future__ import annotations

import json
from typing import Any


def js(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)

