"""기능 4(정산) 담당의 테스트. 공통 함수 queries.is_locked 의 규격(docs/공통모듈_함수규격.md 12절)을 확인한다."""

import copy
import datetime as dt
import json
import unittest

from helpers import NAMES, StoreCase

from moim import cli
from moim.common.money import check_weights, split
from moim.common.queries import expense_shares, expenses_in, is_locked, member_shares
from moim.common.store import EMPTY, Store
from moim.features.settle import balance_sum, balances

KIM, LEE, PARK = NAMES

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


class StoreTransfersTest(StoreCase):
    """store.py EMPTY 의 transfers 항목(기능 4). 함수규격 '기능 4가 더하는 자료 항목' 표."""

    TRANSFER = {"date": "2026-11-20", "from": "신동훈", "to": "양정현", "amount": 3000}

    def test_new_store_has_empty_transfers(self):
        self.assertEqual(Store(self.path("new.json")).data["transfers"], [])

    def test_loaded_empty_store_has_empty_transfers(self):
        self.assertEqual(self.store.data["transfers"], [])

    def test_old_file_without_transfers_gets_default(self):
        old = {"members": [], "expenses": [], "next_id": 1, "locks": [{"start": "2026-11-01", "end": "2026-11-30"}]}
        with open(self.path("old.json"), "w", encoding="utf-8") as f:
            json.dump(old, f)
        s = Store(self.path("old.json")).load()
        self.assertEqual(s.data["transfers"], [])
        self.assertEqual(s.data["locks"], [{"start": "2026-11-01", "end": "2026-11-30"}])

    def test_transfers_survive_save_and_load(self):
        self.store.data["transfers"].append(dict(self.TRANSFER))
        self.store.save()
        s = Store(self.store.path).load()
        self.assertEqual(s.data["transfers"], [self.TRANSFER])

    def test_store_does_not_share_empty_transfers(self):
        self.store.data["transfers"].append(dict(self.TRANSFER))
        self.assertEqual(EMPTY["transfers"], [])
        self.assertEqual(Store(self.path("other.json")).data["transfers"], [])


class StoreRecurringTest(StoreCase):
    """store.py EMPTY 의 recurring 항목(기능 4). 함수규격 '기능 4가 더하는 자료 항목' 표."""

    RULE = {"id": 1, "day": 31, "payer": "양정현", "amount": 50000, "members": ["양정현", "신동훈", "이은경"],
            "memo": "동아리방 대관료", "weights": None, "start_month": "2026-11", "last_month": None}

    def test_new_store_has_empty_recurring(self):
        self.assertEqual(Store(self.path("new.json")).data["recurring"], [])

    def test_loaded_empty_store_has_empty_recurring(self):
        self.assertEqual(self.store.data["recurring"], [])

    def test_old_file_without_recurring_gets_default(self):
        old = {"members": [], "expenses": [], "next_id": 1,
               "transfers": [{"date": "2026-11-20", "from": "신동훈", "to": "양정현", "amount": 3000}]}
        with open(self.path("old.json"), "w", encoding="utf-8") as f:
            json.dump(old, f)
        s = Store(self.path("old.json")).load()
        self.assertEqual(s.data["recurring"], [])
        self.assertEqual(s.data["transfers"], old["transfers"])

    def test_recurring_survives_save_and_load(self):
        rule = dict(self.RULE, weights={"양정현": 2}, last_month="2026-11")
        self.store.data["recurring"].append(rule)
        self.store.save()
        s = Store(self.store.path).load()
        self.assertEqual(s.data["recurring"], [rule])

    def test_store_does_not_share_empty_recurring(self):
        self.store.data["recurring"].append(dict(self.RULE))
        self.assertEqual(EMPTY["recurring"], [])
        self.assertEqual(Store(self.path("other.json")).data["recurring"], [])


class BalancesTest(StoreCase):
    """기능 4 기본 필수: 낸 돈·부담할 돈·잔액, 나머지 1원 규약, 정산 기간, 잔액 합 0 검사.
    기능 1의 add_expense 를 기다리지 않도록 지출을 store.data 에 직접 넣는다(팀원별_구현가이드 '다른 사람을 기다리지 않는 법')."""

    S, E = "2026-11-10", "2026-11-20"

    def put(self, eid, date, payer, amount, members=None, **kw):
        e = {"id": eid, "date": date, "payer": payer, "amount": amount, "members": list(members or NAMES),
             "category": None, "memo": "", "deleted": False, "weights": None, "recurring_id": None}
        e.update(kw)
        self.store.data["expenses"].append(e)

    # 1. 사람마다 낸 돈, 부담할 돈, 잔액
    def test_paid_owed_balance(self):
        # test_basic F4Basic.test_balance 와 같은 값
        self.put(1, "2026-11-12", KIM, 9000)
        rows = balances(self.store, self.S, self.E)
        self.assertEqual(rows[KIM], {"paid": 9000, "owed": 3000, "sent": 0, "received": 0, "balance": 6000})
        self.assertEqual(rows[LEE]["balance"], -3000)   # 음수면 보낼 돈
        self.assertEqual(list(rows), NAMES)

    def test_even_split_owed(self):
        # test_basic F4Basic.test_even_split 과 같은 값
        self.put(1, "2026-11-12", LEE, 6000)
        self.assertEqual({n: r["owed"] for n, r in balances(self.store, self.S, self.E).items()},
                         {KIM: 2000, LEE: 2000, PARK: 2000})

    def test_payer_who_is_not_participant(self):
        self.put(1, "2026-11-12", KIM, 6000, members=[LEE, PARK])
        rows = balances(self.store, self.S, self.E)
        self.assertEqual(rows[KIM], {"paid": 6000, "owed": 0, "sent": 0, "received": 0, "balance": 6000})
        self.assertEqual(list(rows), [LEE, PARK, KIM])

    # 2. 나머지 1원은 규약대로(낸 사람부터, 그다음 참여자 목록 순서)
    def test_remainder_follows_rule(self):
        self.put(1, "2026-11-12", LEE, 10000)
        rows = balances(self.store, self.S, self.E)
        self.assertEqual({n: r["owed"] for n, r in rows.items()}, {KIM: 3333, LEE: 3334, PARK: 3333})
        self.put(2, "2026-11-13", KIM, 10001, weights={KIM: 2})
        rows = balances(self.store, self.S, self.E)
        self.assertEqual({n: r["owed"] for n, r in rows.items()}, {KIM: 3333 + 5001, LEE: 3334 + 2500, PARK: 3333 + 2500})

    # 3. 정산 기간 지정(양끝 포함, 삭제 제외)
    def test_period(self):
        # test_basic F4Basic.test_period 와 같은 값
        self.put(1, "2026-11-05", KIM, 3000)
        self.put(2, "2026-11-12", KIM, 6000)
        self.assertEqual(balances(self.store, self.S, self.E)[KIM]["paid"], 6000)

    def test_period_ends_included_and_deleted_excluded(self):
        self.put(1, "2026-11-10", KIM, 300)
        self.put(2, "2026-11-20", KIM, 600)
        self.put(3, "2026-11-21", KIM, 9000)
        self.put(4, "2026-11-15", KIM, 9000, deleted=True)
        self.assertEqual(balances(self.store, self.S, self.E)[KIM]["paid"], 900)
        self.assertEqual(balances(self.store, None, None)[KIM]["paid"], 9900)

    def test_empty_period_and_bad_period(self):
        self.put(1, "2026-11-12", KIM, 9000)
        self.assertEqual(balances(self.store, "2026-12-01", "2026-12-31"), {})
        with self.assertRaises(ValueError):
            balances(self.store, self.E, self.S)

    def test_transfers_in_period_change_balance(self):
        self.put(1, "2026-11-12", KIM, 9000)
        self.store.data["transfers"] = [
            {"date": "2026-11-15", "from": LEE, "to": KIM, "amount": 3000},
            {"date": "2026-11-25", "from": PARK, "to": KIM, "amount": 3000},   # 기간 밖
        ]
        rows = balances(self.store, self.S, self.E)
        self.assertEqual((rows[LEE]["sent"], rows[LEE]["balance"]), (3000, 0))
        self.assertEqual((rows[KIM]["received"], rows[KIM]["balance"]), (3000, 3000))
        self.assertEqual(rows[PARK]["balance"], -3000)

    def test_bad_transfer_raises(self):
        self.store.data["transfers"] = [{"date": "2026-11-15", "from": LEE, "to": KIM, "amount": 0}]
        with self.assertRaises(ValueError):
            balances(self.store, self.S, self.E)

    # 4. 모든 사람의 잔액 합이 0인지 검사
    def test_balance_sum_is_zero(self):
        # test_basic F4Basic.test_balance_sum 과 같은 값
        self.put(1, "2026-11-12", KIM, 9000)
        self.put(2, "2026-11-13", LEE, 3000)
        self.assertEqual(balance_sum(balances(self.store, self.S, self.E)), 0)

    def test_balance_sum_zero_with_remainders_weights_transfers(self):
        self.put(1, "2026-11-12", KIM, 10001, weights={KIM: 2})
        self.put(2, "2026-11-13", PARK, 7, members=[LEE, PARK])
        self.store.data["transfers"] = [{"date": "2026-11-14", "from": LEE, "to": KIM, "amount": 1234}]
        self.assertEqual(balance_sum(balances(self.store, self.S, self.E)), 0)

    def test_balance_sum_detects_nonzero(self):
        rows = {KIM: {"balance": 10}, LEE: {"balance": -3}}
        self.assertEqual(balance_sum(rows), 7)
        self.assertEqual(balance_sum({}), 0)
        with self.assertRaises(ValueError):
            balance_sum([1, 2])


class SettleCommandTest(StoreCase):
    """명령 `python -m moim settle show` (moim/commands/settle.py)."""

    def run_cmd(self, argv):
        lines = []
        args = cli.build_parser().parse_args(argv)
        changed = cli.run(args, self.cfg, self.store, lines.append)
        return changed, "\n".join(lines)

    def test_show_prints_table_and_zero_sum(self):
        self.store.data["expenses"].append({"id": 1, "date": "2026-11-12", "payer": KIM, "amount": 9000,
                                            "members": list(NAMES), "deleted": False})
        changed, text = self.run_cmd(["settle", "show", "--month", "2026-11"])
        self.assertFalse(changed)   # 조회만 하므로 저장하지 않음
        self.assertIn("정산 기간: 2026-11-01 ~ 2026-11-30", text)
        self.assertIn("9,000", text)
        self.assertIn("-3,000", text)
        self.assertIn("잔액 합: 0 (정상)", text)

    def test_show_with_start_end_and_empty(self):
        changed, text = self.run_cmd(["settle", "show", "--start", "2026-12-01", "--end", "2026-12-31"])
        self.assertFalse(changed)
        self.assertIn("정산할 지출이 없습니다", text)

    def test_show_without_period_is_error(self):
        with self.assertRaises(ValueError):
            self.run_cmd(["settle", "show"])

if __name__ == "__main__":
    unittest.main()
