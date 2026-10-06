# -*- coding: utf-8 -*-
'Kiểm tra hồi quy hành vi mock sau khi chia module.'
from __future__ import annotations

import unittest
from lib.checks import self_test




class HarnessTests(unittest.TestCase):
    def test_mock_and_safety(self):
        self_test()

if __name__ == "__main__":
    unittest.main()
