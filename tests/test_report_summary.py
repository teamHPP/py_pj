"""기능 3(월별·기간 보고서) 담당의 테스트. 기간 요약 report.period_summary(기간·분류별·사람별 합계)를 확인한다.

월별 합계 테스트(tests/test_report.py)와 파일을 나눠, 같은 기능 3의 다른 PR과 같은 줄을 고치지 않게 했다.
"""

import copy
import unittest

from helpers import StoreCase

from moim.common.queries import period_total
from moim.features import report

KIM, LEE = "김민수", "이서연"


def expense(eid, date, payer, amount, category="식비", deleted=False):
    """테스트용 지출 한 건. 기능 1의 add_expense 를 거치지 않고 store.data["expenses"] 에 바로 넣는다."""
    return {"id": eid, "date": date, "payer": payer, "amount": amount, "members": [KIM, LEE],
            "category": category, "memo": "", "deleted": deleted, "weights": None, "recurring_id": None}


class PeriodSummaryTest(StoreCase):
    def put(self, *items):
        self.store.data["expenses"].extend(items)

    def test_basic_example(self):
        # tests/test_basic.py F3Basic 과 같은 자료: 10월 지출은 기간 밖
        self.put(expense(1, "2026-10-15", KIM, 3000), expense(2, "2026-11-12", LEE, 6000),
                 expense(3, "2026-11-13", KIM, 9000, category="교통"))
        self.assertEqual(report.period_summary(self.store, "2026-11-10", "2026-11-20"),
                         {"total": 15000, "count": 2,
                          "by_category": {"식비": 6000, "교통": 9000}, "by_person": {LEE: 6000, KIM: 9000}})

    def test_key_order_is_first_appearance(self):
        self.put(expense(1, "2026-11-13", KIM, 9000, category="교통"), expense(2, "2026-11-12", LEE, 6000))
        got = report.period_summary(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(list(got["by_category"]), ["식비", "교통"])
        self.assertEqual(list(got["by_person"]), [LEE, KIM])

    def test_uncategorized(self):
        # 분류가 없으면 규약의 "미분류"로 모인다(category_of)
        self.put(expense(1, "2026-11-12", KIM, 1000, category=None), expense(2, "2026-11-13", KIM, 2000, category=" "))
        self.assertEqual(report.period_summary(self.store, None, None)["by_category"], {"미분류": 3000})

    def test_both_ends_included(self):
        # 규약 3장: 시작일과 끝일 모두 포함
        self.put(expense(1, "2026-10-31", KIM, 1), expense(2, "2026-11-01", KIM, 2),
                 expense(3, "2026-11-30", LEE, 4), expense(4, "2026-12-01", LEE, 8))
        got = report.period_summary(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual((got["total"], got["count"], got["by_person"]), (6, 2, {KIM: 2, LEE: 4}))

    def test_deleted_excluded(self):
        # 규약 6-1: 삭제된 지출은 합계에서 빠진다
        self.put(expense(1, "2026-11-12", KIM, 6000), expense(2, "2026-11-13", LEE, 9000, category="교통", deleted=True))
        self.assertEqual(report.period_summary(self.store, None, None),
                         {"total": 6000, "count": 1, "by_category": {"식비": 6000}, "by_person": {KIM: 6000}})

    def test_empty(self):
        self.assertEqual(report.period_summary(self.store, "2026-11-01", "2026-11-30"),
                         {"total": 0, "count": 0, "by_category": {}, "by_person": {}})

    def test_totals_agree(self):
        # 분류별 합·사람별 합·period_total 이 모두 같은 값
        self.put(expense(1, "2026-11-12", KIM, 6000), expense(2, "2026-11-13", LEE, 1234, category="교통"),
                 expense(3, "2026-11-14", LEE, 9000, category=None))
        got = report.period_summary(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(sum(got["by_category"].values()), got["total"])
        self.assertEqual(sum(got["by_person"].values()), got["total"])
        self.assertEqual(got["total"], period_total(self.store, "2026-11-01", "2026-11-30"))

    def test_store_not_changed(self):
        self.put(expense(1, "2026-11-12", KIM, 6000))
        before = copy.deepcopy(self.store.data)
        report.period_summary(self.store, None, None)
        self.assertEqual(self.store.data, before)

    def test_bad_input(self):
        for start, end in (("2026-11-31", "2026-11-30"),    # 없는 날짜
                           ("2026/11/01", "2026-11-30"),    # 형식 오류
                           ("2026-11-30", "2026-11-01")):   # 시작일 > 끝일
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                report.period_summary(self.store, start, end)
        with self.assertRaisesRegex(ValueError, "^시작일이 끝일보다 늦습니다: 2026-11-30 > 2026-11-01$"):
            report.period_summary(self.store, "2026-11-30", "2026-11-01")
        self.put(expense(1, "2026-11-12", "", 6000))          # 낸 사람이 빈 문자열
        with self.assertRaises(ValueError):
            report.period_summary(self.store, None, None)


if __name__ == "__main__":
    unittest.main()
