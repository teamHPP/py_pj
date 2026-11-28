"""기능 5 확장 필수: 예산의 80%를 넘으면(80% 초과) 미리 경보. 담당: 김정빈

예산은 helpers 의 100,000원, 경보 비율은 helpers 의 0.8. 지출은 store.data 에 직접 넣는다.
"""

from helpers import NAMES, StoreCase

from moim.features import budget


class BudgetWarn(StoreCase):
    def spend(self, date, amount, deleted=False):
        self.store.data["expenses"].append(
            {"id": self.store.new_id(), "date": date, "payer": "김민수", "amount": amount, "members": list(NAMES),
             "category": None, "memo": "", "deleted": deleted, "weights": None, "recurring_id": None})

    def warn(self, cfg=None, today=None):
        return budget.month_status(self.store, self.cfg if cfg is None else cfg, "2026-11", today)["warn"]

    def test_exactly_80_percent_is_not_warn(self):
        self.spend("2026-11-12", 80000)
        self.assertIs(self.warn(), False)

    def test_one_won_over_80_percent_is_warn(self):
        self.spend("2026-11-12", 80001)
        self.assertIs(self.warn(), True)

    def test_over_budget_is_also_warn(self):
        self.spend("2026-11-12", 150000)
        s = budget.month_status(self.store, self.cfg, "2026-11")
        self.assertEqual((s["over"], s["warn"]), (True, True))

    def test_no_spending_is_not_warn(self):
        self.assertIs(self.warn(), False)

    def test_deleted_and_other_month_not_counted(self):
        self.spend("2026-11-12", 80000)
        self.spend("2026-11-13", 5000, deleted=True)
        self.spend("2026-12-01", 5000)
        self.assertIs(self.warn(), False)

    def test_today_counts_only_until_that_day(self):
        self.spend("2026-11-10", 50000)
        self.spend("2026-11-20", 40000)
        self.assertIs(self.warn(today="2026-11-15"), False)
        self.assertIs(self.warn(today="2026-11-20"), True)

    def test_ratio_from_config_and_default(self):
        self.spend("2026-11-12", 60001)
        self.assertIs(self.warn(dict(self.cfg, warn_ratio=0.6)), True)
        self.assertIs(self.warn(dict(self.cfg, warn_ratio=1)), False)
        no_ratio = {"budget": {"monthly": 100000}}            # 설정에 없으면 0.8
        self.assertIs(self.warn(no_ratio), False)
        self.spend("2026-11-13", 20000)                         # 합계 80,001원
        self.assertIs(self.warn(no_ratio), True)

    def test_float_ratio_has_no_rounding_error(self):
        # 100,000 x 0.29 = 29,000 원 (float 로 곱하면 28999.999999999996 이라 29,000원이 경보로 잘못 잡힘)
        self.spend("2026-11-12", 29000)
        self.assertIs(self.warn(dict(self.cfg, warn_ratio=0.29)), False)

    def test_bad_ratio_is_error(self):
        for ratio in (0, -0.5, 1.5, True, "0.8"):
            with self.subTest(ratio=ratio), self.assertRaises(ValueError):
                self.warn(dict(self.cfg, warn_ratio=ratio))
