"""기능 5 확장 필수: 회비 미납자 목록(월별, 그달 1일이나 말일에 회원인 사람이 대상). 담당: 김정빈

명부는 helpers 의 김민수·이서연·박지훈(2026-09-01 가입), 1인당 월 회비는 helpers 의 20,000원.
"""

import json

from helpers import StoreCase

from moim.features import budget


class Unpaid(StoreCase):
    def pay(self, date, member, amount):
        budget.record_payment(self.store, date, member, amount)

    def member(self, name):
        return self.store.member(name)

    def test_nobody_paid(self):
        self.assertEqual(budget.unpaid(self.store, self.cfg, "2026-11"),
                         [("김민수", 0, 20000), ("이서연", 0, 20000), ("박지훈", 0, 20000)])

    def test_paid_partly_fully_and_over(self):
        self.pay("2026-11-02", "김민수", 20000)
        self.pay("2026-11-03", "이서연", 5000)
        self.pay("2026-11-20", "이서연", 5000)     # 같은 달 여러 번이면 더함
        self.pay("2026-11-04", "박지훈", 30000)    # 더 낸 사람은 미납 아님
        self.assertEqual(budget.unpaid(self.store, self.cfg, "2026-11"), [("이서연", 10000, 10000)])

    def test_everyone_paid_is_empty(self):
        for n in ("김민수", "이서연", "박지훈"):
            self.pay("2026-11-02", n, 20000)
        self.assertEqual(budget.unpaid(self.store, self.cfg, "2026-11"), [])

    def test_only_payments_in_that_month_count(self):
        # 규약 3: 그달 1일과 말일 포함, 앞뒤 달은 빠짐
        self.pay("2026-10-31", "김민수", 20000)
        self.pay("2026-12-01", "김민수", 20000)
        self.pay("2026-11-01", "이서연", 10000)
        self.pay("2026-11-30", "이서연", 10000)
        names = [row[0] for row in budget.unpaid(self.store, self.cfg, "2026-11")]
        self.assertEqual(names, ["김민수", "박지훈"])

    def test_member_on_first_or_last_day_is_target(self):
        self.member("김민수")["joined"] = "2026-11-30"   # 말일에만 회원 → 대상
        self.member("이서연")["left"] = "2026-11-01"     # 1일에만 회원 → 대상
        self.member("박지훈")["joined"] = "2026-12-01"   # 그달에 회원 아님 → 대상 아님
        names = [row[0] for row in budget.unpaid(self.store, self.cfg, "2026-11")]
        self.assertEqual(names, ["김민수", "이서연"])

    def test_member_only_in_middle_of_month_is_not_target(self):
        # 공고문 기준: 1일이나 말일에 회원인 사람만 대상
        self.member("박지훈")["joined"] = "2026-11-10"
        self.member("박지훈")["left"] = "2026-11-20"
        names = [row[0] for row in budget.unpaid(self.store, self.cfg, "2026-11")]
        self.assertEqual(names, ["김민수", "이서연"])

    def test_keeps_roster_order(self):
        self.store.data["members"].reverse()
        names = [row[0] for row in budget.unpaid(self.store, self.cfg, "2026-11")]
        self.assertEqual(names, ["박지훈", "이서연", "김민수"])

    def test_zero_dues_is_empty(self):
        cfg = dict(self.cfg, dues={"monthly": 0})
        self.assertEqual(budget.unpaid(self.store, cfg, "2026-11"), [])

    def test_does_not_change_store(self):
        self.pay("2026-11-02", "김민수", 5000)
        before = json.dumps(self.store.data, sort_keys=True)
        budget.unpaid(self.store, self.cfg, "2026-11")
        self.assertEqual(json.dumps(self.store.data, sort_keys=True), before)

    def test_bad_month_or_config_is_error(self):
        for month in ("2026-13", "2026/11", None):
            with self.subTest(month=month), self.assertRaises(ValueError):
                budget.unpaid(self.store, self.cfg, month)
        for cfg in ({}, {"dues": {}}, {"dues": 20000}, {"dues": {"monthly": -1}},
                    {"dues": {"monthly": True}}, {"dues": {"monthly": "20000"}}):
            with self.subTest(cfg=cfg), self.assertRaises(ValueError):
                budget.unpaid(self.store, cfg, "2026-11")
