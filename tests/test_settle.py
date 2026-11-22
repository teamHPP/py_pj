"""기능 4(정산) 담당의 테스트. 공통 함수 queries.is_locked 의 규격(docs/공통모듈_함수규격.md 12절)을 확인한다."""

import copy
import datetime as dt
import json
import unittest

from helpers import StoreCase

from moim.common.money import check_weights, split
from moim.common.queries import expense_shares, expenses_in, is_locked, member_shares
from moim.common.store import EMPTY, Store

NOV = {"start": "2026-11-01", "end": "2026-11-30"}


class IsLockedTest(StoreCase):
    def lock(self, *periods):
        self.store.data["locks"] = [dict(p) for p in periods]

    def test_no_locks_key_is_false(self):
        self.store.data.pop("locks", None)
        self.assertFalse(is_locked(self.store, "2026-11-17"))

    def test_empty_locks_is_false(self):
        self.lock()
        self.assertFalse(is_locked(self.store, "2026-11-17"))

    def test_inside_period(self):
        self.lock(NOV)
        self.assertTrue(is_locked(self.store, "2026-11-17"))

    def test_start_and_end_are_included(self):
        # 규약 3장: 기간은 시작일과 끝일을 모두 포함한다
        self.lock(NOV)
        self.assertTrue(is_locked(self.store, "2026-11-01"))
        self.assertTrue(is_locked(self.store, "2026-11-30"))

    def test_outside_period(self):
        self.lock(NOV)
        self.assertFalse(is_locked(self.store, "2026-10-31"))
        self.assertFalse(is_locked(self.store, "2026-12-01"))

    def test_one_day_period(self):
        self.lock({"start": "2026-11-17", "end": "2026-11-17"})
        self.assertTrue(is_locked(self.store, "2026-11-17"))
        self.assertFalse(is_locked(self.store, "2026-11-18"))

    def test_any_of_several_periods(self):
        self.lock({"start": "2026-09-01", "end": "2026-09-30"}, NOV)
        self.assertTrue(is_locked(self.store, "2026-09-15"))
        self.assertTrue(is_locked(self.store, "2026-11-15"))
        self.assertFalse(is_locked(self.store, "2026-10-15"))

    def test_date_and_datetime_inputs(self):
        self.lock(NOV)
        self.assertTrue(is_locked(self.store, dt.date(2026, 11, 30)))
        self.assertTrue(is_locked(self.store, dt.datetime(2026, 11, 30, 23, 59)))
        self.assertFalse(is_locked(self.store, dt.datetime(2026, 12, 1, 0, 0)))

    def test_bad_on_raises(self):
        self.lock(NOV)
        for bad in (None, "", "2026-02-30", "2026.11.17", "abc"):
            with self.subTest(on=bad), self.assertRaises(ValueError):
                is_locked(self.store, bad)

    def test_bad_on_raises_even_without_locks(self):
        self.lock()
        with self.assertRaises(ValueError):
            is_locked(self.store, "2026-02-30")

    def test_bad_locks_raise(self):
        bad_cases = [
            "2026-11-01~2026-11-30",                    # 목록이 아님
            ["2026-11-01"],                             # dict 가 아님
            [{"start": "2026-11-01"}],                  # end 없음
            [{"start": "2026-11-01", "end": "2026-13-01"}],  # 없는 날짜
            [{"start": "2026-11-30", "end": "2026-11-01"}],  # 시작일 > 끝일
        ]
        for locks in bad_cases:
            with self.subTest(locks=locks), self.assertRaises(ValueError):
                self.store.data["locks"] = locks
                is_locked(self.store, "2026-11-17")

    def test_does_not_change_store(self):
        self.lock(NOV)
        before = copy.deepcopy(self.store.data)
        is_locked(self.store, "2026-11-17")
        self.assertEqual(self.store.data, before)


class StoreLocksTest(StoreCase):
    """store.py EMPTY 의 locks 항목(기능 4). 함수규격 '기능 4가 더하는 자료 항목' 표."""

    def test_new_store_has_empty_locks(self):
        self.assertEqual(Store(self.path("new.json")).data["locks"], [])

    def test_loaded_empty_store_has_empty_locks(self):
        self.assertEqual(self.store.data["locks"], [])

    def test_old_file_without_locks_gets_default(self):
        old = {"members": [], "expenses": [], "next_id": 1}
        with open(self.path("old.json"), "w", encoding="utf-8") as f:
            json.dump(old, f)
        s = Store(self.path("old.json")).load()
        self.assertEqual(s.data["locks"], [])
        self.assertEqual(s.data["next_id"], 1)

    def test_locks_survive_save_and_load(self):
        self.store.data["locks"].append({"start": "2026-11-01", "end": "2026-11-30"})
        self.store.save()
        s = Store(self.store.path).load()
        self.assertEqual(s.data["locks"], [{"start": "2026-11-01", "end": "2026-11-30"}])
        self.assertTrue(is_locked(s, "2026-11-30"))

    def test_store_does_not_share_empty_locks(self):
        self.store.data["locks"].append({"start": "2026-11-01", "end": "2026-11-30"})
        self.assertEqual(EMPTY["locks"], [])
        self.assertEqual(Store(self.path("other.json")).data["locks"], [])


class CheckWeightsTest(unittest.TestCase):
    """money.check_weights(A1). 함수규격 4장 A1절."""

    P = ["양정현", "신동훈", "이은경"]

    def test_none_means_all_one(self):
        self.assertEqual(check_weights(self.P, None), {"양정현": 1, "신동훈": 1, "이은경": 1})

    def test_empty_dict_means_all_one(self):
        self.assertEqual(check_weights(self.P, {}), {"양정현": 1, "신동훈": 1, "이은경": 1})

    def test_missing_names_are_one(self):
        self.assertEqual(check_weights(self.P, {"양정현": 2}), {"양정현": 2, "신동훈": 1, "이은경": 1})

    def test_result_follows_member_order(self):
        result = check_weights(self.P, {"이은경": 1, "양정현": 3, "신동훈": 2})
        self.assertEqual(list(result), self.P)
        self.assertEqual(result, {"양정현": 3, "신동훈": 2, "이은경": 1})

    def test_bad_weights_raise(self):
        bad_cases = [
            "2:1:1",                 # dict 가 아님
            [("양정현", 2)],          # dict 가 아님
            {"김철수": 1},            # 참여자가 아닌 이름
            {"양정현": 0},            # 0
            {"양정현": -1},           # 음수
            {"양정현": True},         # bool
            {"양정현": 1.5},          # 정수가 아님
            {"양정현": "2"},          # 정수가 아님
        ]
        for weights in bad_cases:
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                check_weights(self.P, weights)

    def test_does_not_change_input(self):
        weights = {"양정현": 2}
        members = list(self.P)
        check_weights(members, weights)
        self.assertEqual(weights, {"양정현": 2})
        self.assertEqual(members, self.P)

    def test_returns_new_dict(self):
        weights = {"양정현": 2, "신동훈": 1, "이은경": 1}
        result = check_weights(self.P, weights)
        result["양정현"] = 99
        self.assertEqual(weights["양정현"], 2)


class SplitTest(unittest.TestCase):
    """money.split 비율 분배(기능 4). 함수규격 09절, 규약 2장."""

    P = ["양정현", "신동훈", "이은경"]

    def test_spec_examples(self):
        self.assertEqual(split(100, self.P, payer="신동훈"), {"양정현": 33, "신동훈": 34, "이은경": 33})
        self.assertEqual(split(10000, self.P, payer="양정현"), {"양정현": 3334, "신동훈": 3333, "이은경": 3333})
        self.assertEqual(split(10001, self.P, "양정현", {"양정현": 2}),
                         {"양정현": 5001, "신동훈": 2500, "이은경": 2500})
        self.assertEqual(split(0, self.P), {"양정현": 0, "신동훈": 0, "이은경": 0})

    def test_remainder_goes_payer_first_then_list_order(self):
        # 규약 2장: 남는 원은 낸 사람이 참여자이면 낸 사람부터, 그다음은 참여자 목록 순서
        self.assertEqual(split(7, self.P, "이은경", {"신동훈": 2}), {"양정현": 2, "신동훈": 3, "이은경": 2})

    def test_payer_not_member_uses_list_order(self):
        self.assertEqual(split(10001, self.P, "김철수", {"양정현": 2}),
                         {"양정현": 5001, "신동훈": 2500, "이은경": 2500})

    def test_sum_is_always_amount(self):
        for amount in (0, 1, 7, 100, 9999, 10001):
            for weights in (None, {}, {"양정현": 2}, {"양정현": 1, "신동훈": 1, "이은경": 3}, {"이은경": 7}):
                for payer in (None, "양정현", "이은경", "김철수"):
                    with self.subTest(amount=amount, weights=weights, payer=payer):
                        result = split(amount, self.P, payer, weights)
                        self.assertEqual(sum(result.values()), amount)
                        self.assertEqual(list(result), self.P)

    def test_empty_weights_same_as_even(self):
        self.assertEqual(split(9000, self.P, weights={}), split(9000, self.P))
        self.assertEqual(split(9000, self.P, weights=None), {"양정현": 3000, "신동훈": 3000, "이은경": 3000})

    def test_bad_inputs_raise(self):
        bad_cases = [
            (True, self.P, None, None),             # bool 금액
            (9000.0, self.P, None, None),           # 정수가 아닌 금액
            ("9000", self.P, None, None),           # 문자열 금액
            (-1, self.P, None, None),               # 음수
            (100, [], None, None),                  # 빈 참여자
            (100, ["양정현", "양정현"], None, None),  # 중복 참여자
            (100, self.P, 3, None),                 # 잘못된 payer 자료형
            (100, self.P, None, {"김철수": 1}),       # check_weights 가 거부
            (100, self.P, None, {"양정현": 0}),       # check_weights 가 거부
        ]
        for args in bad_cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                split(*args)

    def test_does_not_change_input(self):
        members, weights = list(self.P), {"양정현": 2}
        split(10001, members, "양정현", weights)
        self.assertEqual(members, self.P)
        self.assertEqual(weights, {"양정현": 2})


class ExpenseSharesTest(unittest.TestCase):
    """queries.expense_shares(기능 4). 함수규격 10절."""

    P = ["양정현", "신동훈", "이은경"]

    def expense(self, **kw):
        e = {"id": 1, "date": "2026-11-17", "payer": "양정현", "amount": 9000, "members": list(self.P),
             "category": "식비", "memo": "회의 후 저녁", "deleted": False, "weights": None, "recurring_id": None}
        e.update(kw)
        return e

    def test_spec_example(self):
        self.assertEqual(expense_shares(self.expense()), {"양정현": 3000, "신동훈": 3000, "이은경": 3000})

    def test_same_as_split(self):
        cases = [
            dict(amount=10001, weights={"양정현": 2}),
            dict(amount=100, payer="신동훈"),
            dict(amount=100, payer="김철수"),        # 낸 사람이 참여자가 아니어도 계산
            dict(amount=7, payer="이은경", weights={"신동훈": 2}),
        ]
        for kw in cases:
            with self.subTest(**kw):
                e = self.expense(**kw)
                self.assertEqual(expense_shares(e), split(e["amount"], e["members"], e["payer"], e["weights"]))

    def test_weights_missing_is_even(self):
        e = self.expense()
        del e["weights"]
        self.assertEqual(expense_shares(e), {"양정현": 3000, "신동훈": 3000, "이은경": 3000})

    def test_does_not_check_deleted_or_membership(self):
        # 삭제 제외는 expenses_in(05)이, 명부 검사는 입력할 때 validate 가 맡는다
        self.assertEqual(expense_shares(self.expense(deleted=True)), {"양정현": 3000, "신동훈": 3000, "이은경": 3000})

    def test_bad_expense_raises(self):
        no_amount = self.expense()
        del no_amount["amount"]
        bad_cases = [
            None, [], {},                                     # dict 가 아님 / 빈 지출
            no_amount,                                        # 필수 키 누락
            self.expense(amount=0), self.expense(amount=True), self.expense(amount="9000"),
            self.expense(members=[]), self.expense(members="양정현"), self.expense(members=["양정현", "양정현"]),
            self.expense(members=["  "]), self.expense(members=["양정현", ""]),  # 공백뿐·빈 이름(낸 사람과 같은 기준)
            self.expense(payer=""), self.expense(payer=None),
            self.expense(weights={"김철수": 1}),
        ]
        for e in bad_cases:
            with self.subTest(e=e), self.assertRaises(ValueError):
                expense_shares(e)

    def test_does_not_change_expense(self):
        e = self.expense(amount=10001, weights={"양정현": 2})
        before = copy.deepcopy(e)
        result = expense_shares(e)
        result["양정현"] = 0
        self.assertEqual(e, before)


class MemberSharesTest(StoreCase):
    """queries.member_shares(기능 4). 함수규격 11절. 예시 자료 S 의 명부·지출 e 로 확인한다."""

    P = ["양정현", "신동훈", "이은경"]

    def setUp(self):
        super().setUp()
        self.store.data["members"] = [
            {"name": "양정현", "joined": "2026-09-01", "left": None},
            {"name": "신동훈", "joined": "2026-09-01", "left": "2026-11-30"},
            {"name": "이은경", "joined": "2026-09-01", "left": None},
        ]
        self.put(self.expense(1, "2026-11-17"))   # 함수규격 2장 예시 자료 S 의 e (양정현 9000, 3명)

    def expense(self, eid, date, amount=9000, **kw):
        e = {"id": eid, "date": date, "payer": "양정현", "amount": amount, "members": list(self.P),
             "category": None, "memo": "", "deleted": False, "weights": None, "recurring_id": None}
        e.update(kw)
        return e

    def put(self, *items):
        self.store.data["expenses"].extend(items)

    def test_spec_examples(self):
        self.assertEqual(member_shares(self.store, "2026-11-01", "2026-11-30"),
                         {"양정현": 3000, "신동훈": 3000, "이은경": 3000})
        self.assertEqual(member_shares(self.store, "2026-12-01", "2026-12-31"), {})
        self.assertEqual(member_shares(self.store, None, None), {"양정현": 3000, "신동훈": 3000, "이은경": 3000})

    def test_sums_expense_shares_with_weights(self):
        self.put(self.expense(2, "2026-11-18", 10001, weights={"양정현": 2}))
        self.assertEqual(member_shares(self.store, None, None), {"양정현": 8001, "신동훈": 5500, "이은경": 5500})

    def test_both_ends_included(self):
        # 규약 3장: 기간은 시작일과 끝일을 모두 포함한다
        self.put(self.expense(2, "2026-10-31", 300), self.expense(3, "2026-11-01", 30),
                 self.expense(4, "2026-11-30", 3), self.expense(5, "2026-12-01", 3000))
        self.assertEqual(member_shares(self.store, "2026-11-01", "2026-11-30"),
                         {"양정현": 3011, "신동훈": 3011, "이은경": 3011})

    def test_deleted_is_excluded(self):
        # 규약 6-1장: 삭제된 지출은 정산에서 빠진다
        self.put(self.expense(2, "2026-11-18", 600, deleted=True))
        self.assertEqual(member_shares(self.store, None, None), {"양정현": 3000, "신동훈": 3000, "이은경": 3000})

    def test_zero_share_is_kept_and_non_participant_left_out(self):
        self.store.data["expenses"] = [self.expense(1, "2026-11-17", 1, members=["양정현", "이은경"])]
        self.assertEqual(member_shares(self.store, None, None), {"양정현": 1, "이은경": 0})

    def test_key_order_follows_expenses_in(self):
        # expenses_in 은 (date, id) 오름차순. 더 이른 지출의 참여자 순서가 먼저 온다
        self.put(self.expense(2, "2026-11-05", 2000, payer="이은경", members=["이은경", "신동훈"]))
        self.assertEqual(list(member_shares(self.store, None, None)), ["이은경", "신동훈", "양정현"])

    def test_left_member_past_share_counted(self):
        # 신동훈은 11-30 탈퇴. 그 전 지출의 부담액은 그대로 센다
        self.assertEqual(member_shares(self.store, None, None)["신동훈"], 3000)

    def test_sum_equals_expenses_in_total(self):
        self.put(self.expense(2, "2026-11-18", 10001, weights={"양정현": 2}),
                 self.expense(3, "2026-11-19", 7, payer="이은경", weights={"신동훈": 2}))
        got = member_shares(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(sum(got.values()),
                         sum(x["amount"] for x in expenses_in(self.store, "2026-11-01", "2026-11-30")))

    def test_errors_come_from_expenses_in_and_expense_shares(self):
        with self.assertRaisesRegex(ValueError, "^시작일이 끝일보다 늦습니다: "):
            member_shares(self.store, "2026-11-30", "2026-11-01")
        self.put(self.expense(2, "2026-11-18", weights={"김철수": 1}))
        with self.assertRaises(ValueError):
            member_shares(self.store, None, None)

    def test_does_not_change_store(self):
        self.put(self.expense(2, "2026-11-18", 10001, weights={"양정현": 2}))
        before = copy.deepcopy(self.store.data)
        result = member_shares(self.store, None, None)
        result["양정현"] = 0
        self.assertEqual(self.store.data, before)

if __name__ == "__main__":
    unittest.main()
