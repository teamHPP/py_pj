"""기능 5 확장 필수: 분류별 예산과 분류별 초과 경보. 담당: 김정빈

설정은 helpers 의 분류별 예산 {"식비": 50000}, 경보 비율 0.8. 지출은 store.data 에 직접 넣는다.
"""

import json

from helpers import NAMES, StoreCase

from moim.features import budget


class CategoryStatus(StoreCase):
    def spend(self, date, amount, category, deleted=False):
        self.store.data["expenses"].append(
            {"id": self.store.new_id(), "date": date, "payer": "김민수", "amount": amount, "members": list(NAMES),
             "category": category, "memo": "", "deleted": deleted, "weights": None, "recurring_id": None})

    def status(self, cfg=None, month="2026-11"):
        return budget.category_status(self.store, self.cfg if cfg is None else cfg, month)

    def test_basic(self):
        self.spend("2026-11-12", 30000, "식비")
        self.assertEqual(self.status(), {"식비": {"budget": 50000, "spent": 30000, "remaining": 20000,
                                                "over": False, "warn": False}})

    def test_warn_and_over_boundaries(self):
        # 80% = 40,000원: 정확히는 경보 아님, 1원 넘으면 경보 / 정확히 예산은 초과 아님, 1원 넘으면 초과
        cases = [(40000, False, False), (40001, False, True), (50000, False, True), (50001, True, True)]
        for amount, over, warn in cases:
            self.store.data["expenses"] = []
            self.spend("2026-11-12", amount, "식비")
            s = self.status()["식비"]
            with self.subTest(amount=amount):
                self.assertEqual((s["over"], s["warn"], s["remaining"]), (over, warn, 50000 - amount))

    def test_category_without_spending_is_zero(self):
        self.spend("2026-11-12", 9000, "교통")   # 예산이 없는 분류는 결과에 없음
        self.assertEqual(self.status()["식비"]["spent"], 0)
        self.assertNotIn("교통", self.status())

    def test_only_that_month_and_not_deleted(self):
        self.spend("2026-10-31", 1, "식비")
        self.spend("2026-11-01", 20, "식비")
        self.spend("2026-11-30", 300, "식비")
        self.spend("2026-12-01", 4000, "식비")
        self.spend("2026-11-15", 50000, "식비", deleted=True)
        self.assertEqual(self.status()["식비"]["spent"], 320)

    def test_uncategorized_budget_uses_category_of(self):
        # 분류가 None·공백·키 없음이면 category_of 가 "미분류"로 묶는다
        cfg = dict(self.cfg, budget={"monthly": 100000, "by_category": {"미분류": 10000}})
        self.spend("2026-11-12", 1000, None)
        self.spend("2026-11-13", 2000, "  ")
        self.store.data["expenses"].append({"id": self.store.new_id(), "date": "2026-11-14", "payer": "김민수",
                                            "amount": 4000, "members": list(NAMES), "deleted": False})
        self.assertEqual(self.status(cfg)["미분류"]["spent"], 7000)

    def test_keeps_config_order_and_ratio(self):
        cfg = dict(self.cfg, warn_ratio=0.5,
                   budget={"monthly": 100000, "by_category": {"교통": 10000, "식비": 50000}})
        self.spend("2026-11-12", 5001, "교통")
        result = self.status(cfg)
        self.assertEqual(list(result), ["교통", "식비"])
        self.assertIs(result["교통"]["warn"], True)

    def test_spaces_around_config_name_match_category_of(self):
        # 리뷰(#72) 반영: 설정 이름의 앞뒤 공백을 지워 category_of 와 같은 기준으로 맞춘다
        self.spend("2026-11-12", 45000, "식비")
        for name in (" 식비", "식비 ", " 식비 "):
            cfg = dict(self.cfg, budget={"monthly": 100000, "by_category": {name: 50000}})
            with self.subTest(name=name):
                self.assertEqual(self.status(cfg),
                                 {"식비": {"budget": 50000, "spent": 45000, "remaining": 5000,
                                          "over": False, "warn": True}})

    def test_no_category_budgets_is_empty(self):
        self.assertEqual(self.status({"budget": {"monthly": 100000}}), {})

    def test_does_not_change_store(self):
        self.spend("2026-11-12", 30000, "식비")
        before = json.dumps(self.store.data, sort_keys=True)
        self.status()
        self.assertEqual(json.dumps(self.store.data, sort_keys=True), before)

    def test_bad_input_is_error(self):
        with self.assertRaises(ValueError):
            self.status(month="2026-13")
        for by_category in ([("식비", 1000)], {"식비": -1}, {"식비": True}, {"식비": "1000"}, {"": 1000},
                            {"식비": 1000, " 식비": 2000}):   # 공백을 지우면 겹치는 이름
            cfg = dict(self.cfg, budget={"monthly": 100000, "by_category": by_category})
            with self.subTest(by_category=by_category), self.assertRaises(ValueError):
                self.status(cfg)
