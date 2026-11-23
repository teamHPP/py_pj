"""기능 3(월별·기간 보고서) 담당의 테스트. 공통 함수 queries.expenses_in·person_paid 의 규격(docs/공통모듈_함수규격.md 05·06절)과 보고서 함수를 확인한다."""

import copy
import datetime as dt
import unittest
from unittest import mock

from helpers import StoreCase

from moim.common.queries import expenses_in, period_total, person_paid
from moim.features import report

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


class PersonPaidTest(StoreCase):
    def setUp(self):
        super().setUp()
        self.e = expense(1, "2026-11-17")   # 규격 2장 예시 자료 S 의 e (양정현 9000)
        self.store.data["expenses"].append(self.e)

    def put(self, *items):
        self.store.data["expenses"].extend(items)

    def test_spec_examples(self):
        self.assertEqual(person_paid(self.store, "2026-11-01", "2026-11-30"), {"양정현": 9000})
        self.assertEqual(person_paid(self.store, "2026-12-01", "2026-12-31"), {})
        self.put(expense(2, "2026-11-18", 3000, payer="이은경", category=None, memo=""))
        self.assertEqual(person_paid(self.store, None, None), {"양정현": 9000, "이은경": 3000})

    def test_same_payer_is_summed(self):
        self.put(expense(2, "2026-11-20", 1000))
        self.assertEqual(person_paid(self.store, None, None), {"양정현": 10000})

    def test_key_order_follows_expenses_in(self):
        # key 순서는 expenses_in 결과((date, id) 오름차순)에서 처음 나온 순서
        self.put(expense(2, "2026-11-05", 3000, payer="이은경"))
        self.assertEqual(list(person_paid(self.store, None, None)), ["이은경", "양정현"])

    def test_both_ends_included(self):
        # 규약 3장: 기간은 시작일과 끝일을 모두 포함한다
        self.put(expense(2, "2026-10-31", 1, payer="이은경"), expense(3, "2026-11-01", 2, payer="이은경"),
                 expense(4, "2026-11-30", 4, payer="이은경"), expense(5, "2026-12-01", 8, payer="이은경"))
        self.assertEqual(person_paid(self.store, "2026-11-01", "2026-11-30"), {"이은경": 6, "양정현": 9000})

    def test_deleted_is_excluded(self):
        # 규약 6-1: 삭제된 지출은 합계에서 빠진다
        self.e["deleted"] = True
        self.assertEqual(person_paid(self.store, None, None), {})

    def test_left_member_still_counted(self):
        # 지금 탈퇴한 사람이라도 과거에 낸 돈은 그대로 센다
        self.put(expense(2, "2026-11-20", 5000, payer="신동훈"))
        self.assertEqual(person_paid(self.store, None, None)["신동훈"], 5000)

    def test_sum_equals_total_of_expenses_in(self):
        # 모든 값의 합은 같은 기간 expenses_in 금액 합(= 19 period_total)과 같다
        self.put(expense(2, "2026-11-18", 3000, payer="이은경"), expense(3, "2026-11-19", 1234, payer="신동훈"))
        got = person_paid(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(sum(got.values()),
                         sum(x["amount"] for x in expenses_in(self.store, "2026-11-01", "2026-11-30")))

    def test_new_dict_and_store_not_changed(self):
        before = [dict(x) for x in self.store.data["expenses"]]
        first = person_paid(self.store, None, None)
        first["양정현"] = 0
        self.assertEqual(person_paid(self.store, None, None), {"양정현": 9000})
        self.assertEqual(self.store.data["expenses"], before)

    def test_reversed_period_error(self):
        # expenses_in(05) 의 오류를 그대로 올린다
        with self.assertRaisesRegex(ValueError, "^시작일이 끝일보다 늦습니다: "):
            person_paid(self.store, "2026-11-30", "2026-11-01")

    def test_bad_payer(self):
        for payer in ("", "  ", None, 3):
            with self.subTest(payer=payer):
                self.store.data["expenses"] = [expense(1, "2026-11-17", payer=payer)]
                with self.assertRaises(ValueError):
                    person_paid(self.store, None, None)


class MonthlyTotalsTest(StoreCase):
    """기본 필수: 월별 지출 합계. 지출은 store.data 에 바로 넣는다."""

    def put(self, *items):
        self.store.data["expenses"].extend(items)

    def test_basic_example(self):
        # tests/test_basic.py F3Basic.test_monthly 와 같은 자료
        self.put(expense(1, "2026-10-15", 3000), expense(2, "2026-11-12", 6000), expense(3, "2026-11-13", 9000))
        self.assertEqual(report.monthly_totals(self.store, "2026-11", "2026-11"), {"2026-11": 15000})

    def test_every_month_in_order_with_zero(self):
        # 지출이 없는 달(12월)도 0으로 넣고, 해가 바뀌어도 달 순서대로
        self.put(expense(1, "2027-01-03", 500), expense(2, "2026-10-15", 3000), expense(3, "2026-11-12", 6000))
        got = report.monthly_totals(self.store, "2026-10", "2027-01")
        self.assertEqual(got, {"2026-10": 3000, "2026-11": 6000, "2026-12": 0, "2027-01": 500})
        self.assertEqual(list(got), ["2026-10", "2026-11", "2026-12", "2027-01"])

    def test_first_and_last_day_included(self):
        # 규약 3장: 그달 1일과 말일 모두 포함, 앞뒤 달은 빠짐
        self.put(expense(1, "2026-10-31", 1), expense(2, "2026-11-01", 2),
                 expense(3, "2026-11-30", 4), expense(4, "2026-12-01", 8))
        self.assertEqual(report.monthly_totals(self.store, "2026-11", "2026-11"), {"2026-11": 6})

    def test_deleted_excluded(self):
        # 규약 6-1: 삭제된 지출은 합계에서 빠진다
        self.put(expense(1, "2026-11-12", 6000), expense(2, "2026-11-13", 9000, deleted=True))
        self.assertEqual(report.monthly_totals(self.store, "2026-11", "2026-11"), {"2026-11": 6000})

    def test_empty(self):
        self.assertEqual(report.monthly_totals(self.store, "2026-11", "2026-12"), {"2026-11": 0, "2026-12": 0})

    def test_same_as_period_total(self):
        # 달마다 값이 같은 달의 period_total(19)과 같다
        self.put(expense(1, "2026-11-12", 6000), expense(2, "2026-12-24", 1234), expense(3, "2026-12-31", 9000))
        got = report.monthly_totals(self.store, "2026-11", "2026-12")
        self.assertEqual(got["2026-11"], period_total(self.store, "2026-11-01", "2026-11-30"))
        self.assertEqual(got["2026-12"], period_total(self.store, "2026-12-01", "2026-12-31"))

    def test_store_not_changed(self):
        self.put(expense(1, "2026-11-12", 6000))
        before = copy.deepcopy(self.store.data)
        report.monthly_totals(self.store, "2026-11", "2026-11")
        self.assertEqual(self.store.data, before)

    def test_bad_month(self):
        for start, end in (("2026-13", "2026-12"), ("2026/11", "2026-11"), ("202611", "2026-11"),
                           ("2026-11-01", "2026-11"), (None, "2026-11"),
                           ("2026-12", "2026-11")):   # 시작 달 > 끝 달
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                report.monthly_totals(self.store, start, end)

    def test_reversed_months_checked_before_months_between(self):
        # 규격 1장 ⚠·17 주의: months_between 의 ValueError 에 기대지 않는다.
        # 채점 때 바뀐 months_between 이 거꾸로 된 달에 [] 를 돌려줘도 같은 ValueError
        with mock.patch("moim.common.dates.months_between", return_value=[]):
            with self.assertRaisesRegex(ValueError, "^시작 달이 끝 달보다 뒤입니다: 2026-12 > 2026-11$"):
                report.monthly_totals(self.store, "2026-12", "2026-11")


if __name__ == "__main__":
    unittest.main()
