"""기능 3(월별·기간 보고서) 담당의 테스트. 공통 함수 queries.expenses_in 의 규격(docs/공통모듈_함수규격.md 05절)을 확인한다."""

import datetime as dt
import unittest

from helpers import StoreCase

from moim.common.queries import expenses_in

P = ["양정현", "신동훈", "이은경"]


def expense(eid, date, amount=9000, **kw):
    """테스트용 지출 한 건. 기능 1의 insert 를 거치지 않고 store.data["expenses"] 에 바로 넣는다."""
    e = {"id": eid, "date": date, "payer": "양정현", "amount": amount, "members": list(P),
         "category": "식비", "memo": "회의 후 저녁", "deleted": False, "weights": None, "recurring_id": None}
    e.update(kw)
    return e


class ExpensesInTest(StoreCase):
    def setUp(self):
        super().setUp()
        self.e = expense(1, "2026-11-17")   # 규격 2장 예시 자료 S 의 e
        self.store.data["expenses"].append(self.e)

    def put(self, *items):
        self.store.data["expenses"].extend(items)

    def ids(self, start, end, **kw):
        return [x["id"] for x in expenses_in(self.store, start, end, **kw)]

    def test_spec_examples(self):
        self.assertEqual(expenses_in(self.store, "2026-11-17", "2026-11-17"), [self.e])
        self.assertEqual(expenses_in(self.store, "2026-11-01", "2026-11-30"), [self.e])
        self.assertEqual(expenses_in(self.store, None, None), [self.e])
        self.assertEqual(expenses_in(self.store, "2026-12-01", "2026-12-31"), [])

    def test_both_ends_included(self):
        # 규약 3장: 기간은 시작일과 끝일을 모두 포함한다
        self.put(expense(2, "2026-10-31"), expense(3, "2026-11-01"),
                 expense(4, "2026-11-30"), expense(5, "2026-12-01"))
        self.assertEqual(self.ids("2026-11-01", "2026-11-30"), [3, 1, 4])

    def test_none_means_no_limit(self):
        self.put(expense(2, "2026-01-01"), expense(3, "2027-12-31"))
        self.assertEqual(self.ids(None, "2026-11-16"), [2])
        self.assertEqual(self.ids("2026-11-17", None), [1, 3])

    def test_order_by_date_then_id(self):
        self.put(expense(3, "2026-11-05"), expense(2, "2026-11-17"), expense(4, "2026-11-05"))
        self.assertEqual(self.ids(None, None), [3, 4, 1, 2])

    def test_date_and_datetime_input(self):
        self.assertEqual(self.ids(dt.date(2026, 11, 17), dt.datetime(2026, 11, 17, 23, 59)), [1])

    def test_deleted(self):
        # 규약 6-1: 삭제된 지출은 따로 요청할 때만 보인다
        self.e["deleted"] = True
        self.put(expense(2, "2026-11-18"))
        self.assertEqual(self.ids(None, None), [2])
        self.assertEqual(self.ids(None, None, include_deleted=True), [1, 2])

    def test_missing_deleted_key_is_false(self):
        del self.e["deleted"]
        self.assertEqual(self.ids(None, None), [1])

    def test_result_is_deep_copy(self):
        got = expenses_in(self.store, None, None)
        got[0]["amount"] = 1
        got[0]["members"].append("없는사람")
        self.assertEqual(self.e["amount"], 9000)
        self.assertEqual(self.e["members"], P)

    def test_store_not_changed(self):
        before = [dict(x) for x in self.store.data["expenses"]]
        expenses_in(self.store, None, None, include_deleted=True)
        self.assertEqual(self.store.data["expenses"], before)

    def test_empty(self):
        self.store.data["expenses"] = []
        self.assertEqual(expenses_in(self.store, None, None), [])
        self.store.data["expenses"] = [expense(1, "2026-11-17", deleted=True)]
        self.assertEqual(expenses_in(self.store, None, None), [])

    def test_reversed_period_message(self):
        # 04·11·19 가 그대로 올리는 오류 문구의 기준
        with self.assertRaisesRegex(ValueError, "^시작일이 끝일보다 늦습니다: "):
            expenses_in(self.store, "2026-11-30", "2026-11-01")

    def test_bad_arguments(self):
        for start, end, flag in (("2026-02-30", None, False),          # 없는 날짜
                                 ("2026/11/01", None, False),          # 형식 오류
                                 ("2026-11-30", "2026-11-01", False),  # 역순 기간
                                 (None, None, "yes"),                  # bool 이 아님
                                 (None, None, 1)):
            with self.subTest(start=start, end=end, flag=flag), self.assertRaises(ValueError):
                expenses_in(self.store, start, end, include_deleted=flag)

    def test_bad_expense_data(self):
        bad = ({"id": True}, {"id": "2"}, {"date": 20261117}, {"date": "2026-13-01"},
               {"date": "2026-1-5"}, {"amount": 0}, {"amount": -1}, {"amount": True},
               {"amount": "9000"}, {"amount": 9000.0}, {"deleted": "yes"})
        for change in bad:
            with self.subTest(change=change):
                # 기간 밖(2025년) 지출이어도 검사한다
                self.store.data["expenses"] = [self.e, {**expense(2, "2025-01-01"), **change}]
                with self.assertRaises(ValueError):
                    expenses_in(self.store, "2026-11-01", "2026-11-30")

    def test_bad_expense_list(self):
        self.store.data["expenses"] = [self.e, "지출 아님"]
        with self.assertRaises(ValueError):
            expenses_in(self.store, None, None)


if __name__ == "__main__":
    unittest.main()
