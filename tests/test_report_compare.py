"""기능 3(월별·기간 보고서) 담당의 테스트. 전월 대비 report.month_over_month 와 월 보고서의 전월 대비 줄을 확인한다.

다른 기능 3 테스트 파일과 나눠, 같은 기능 3의 다른 PR과 같은 줄을 고치지 않게 했다.
"""

import copy
import unittest

from helpers import StoreCase

from moim.common.queries import period_total
from moim.features import report

KIM = "김민수"


def expense(eid, date, amount, deleted=False):
    """테스트용 지출 한 건. 기능 1의 add_expense 를 거치지 않고 store.data["expenses"] 에 바로 넣는다."""
    return {"id": eid, "date": date, "payer": KIM, "amount": amount, "members": [KIM],
            "category": "식비", "memo": "", "deleted": deleted, "weights": None, "recurring_id": None}


class MonthOverMonthTest(StoreCase):
    def put(self, *items):
        self.store.data["expenses"].extend(items)

    def test_increase_and_decrease(self):
        self.put(expense(1, "2026-10-05", 3000), expense(2, "2026-11-12", 4000), expense(3, "2026-12-01", 1000))
        self.assertEqual(report.month_over_month(self.store, "2026-11"), (4000, 3000, 1000, 33.3))
        self.assertEqual(report.month_over_month(self.store, "2026-12"), (1000, 4000, -3000, -75.0))

    def test_last_month_zero_rate_is_none(self):
        # 지난달 지출이 0원이면 증감률을 계산하지 않는다(확장 필수: 증감률 대신 안내 문구)
        self.put(expense(1, "2026-11-12", 4000))
        self.assertEqual(report.month_over_month(self.store, "2026-11"), (4000, 0, 4000, None))
        self.assertEqual(report.month_over_month(self.store, "2026-09"), (0, 0, 0, None))

    def test_this_month_zero(self):
        self.put(expense(1, "2026-10-05", 3000))
        self.assertEqual(report.month_over_month(self.store, "2026-11"), (0, 3000, -3000, -100.0))

    def test_rate_rounds_half_up(self):
        # 규약 1장: 사사오입(파이썬 round() 는 0.05 경계에서 다르게 나올 수 있어 쓰지 않는다)
        self.put(expense(1, "2026-10-05", 2000), expense(2, "2026-11-12", 2001))   # 0.05% → 0.1%
        self.assertEqual(report.month_over_month(self.store, "2026-11")[3], 0.1)
        self.store.data["expenses"] = [expense(1, "2026-10-05", 2000), expense(2, "2026-11-12", 1999)]
        self.assertEqual(report.month_over_month(self.store, "2026-11")[3], -0.1)   # -0.05% → -0.1%

    def test_month_bounds_year_change_and_deleted(self):
        # 그달 1일·말일 포함(규약 3), 1월의 지난달은 전년 12월, 삭제된 지출은 빠짐(규약 6-1)
        self.put(expense(1, "2025-12-01", 1000), expense(2, "2025-12-31", 1000), expense(3, "2025-11-30", 50),
                 expense(4, "2026-01-01", 3000), expense(5, "2026-01-31", 1000, deleted=True))
        self.assertEqual(report.month_over_month(self.store, "2026-01"), (3000, 2000, 1000, 50.0))

    def test_same_as_period_total(self):
        self.put(expense(1, "2026-10-05", 3000), expense(2, "2026-11-12", 4000))
        this, last, _, _ = report.month_over_month(self.store, "2026-11")
        self.assertEqual((this, last), (period_total(self.store, "2026-11-01", "2026-11-30"),
                                        period_total(self.store, "2026-10-01", "2026-10-31")))

    def test_store_not_changed_and_bad_month(self):
        self.put(expense(1, "2026-10-05", 3000))
        before = copy.deepcopy(self.store.data)
        report.month_over_month(self.store, "2026-11")
        self.assertEqual(self.store.data, before)
        for bad in ("2026-13", "2026/11", "2026-11-01", None):
            with self.subTest(month=bad), self.assertRaises(ValueError):
                report.month_over_month(self.store, bad)


class MonthReportCompareLineTest(StoreCase):
    def line(self, month):
        return report.month_report(self.store, month).split("\n")[1]

    def test_with_rate(self):
        self.store.data["expenses"].extend([expense(1, "2026-10-05", 3000), expense(2, "2026-11-12", 4000)])
        self.assertEqual(self.line("2026-11"), "합계 4,000원 (1건), 지난달 3,000원, 증감 +1,000원 (+33.3%)")

    def test_last_month_zero_message(self):
        # 스켈레톤 안내서 8장 월 보고서와 같은 모양
        self.store.data["expenses"].append(expense(1, "2026-11-12", 1512900))
        self.assertEqual(self.line("2026-11"),
                         "합계 1,512,900원 (1건), 지난달 0원, 증감 +1,512,900원 (비교할 지난달 지출 없음)")

    def test_no_change(self):
        self.store.data["expenses"].extend([expense(1, "2026-10-05", 3000), expense(2, "2026-11-12", 3000)])
        self.assertEqual(self.line("2026-11"), "합계 3,000원 (1건), 지난달 3,000원, 증감 +0원 (+0.0%)")


if __name__ == "__main__":
    unittest.main()
