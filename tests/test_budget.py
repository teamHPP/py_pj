"""기능 5(예산·회비) 테스트. 담당: 김정빈

공통 함수 테스트는 docs/공통모듈_함수규격.md 의 예시 자료 S 명부로 확인한다.
"""

import datetime as dt
import json
import unittest

from helpers import NAMES, StoreCase

from moim.common import dates
from moim.common.dates import months_between
from moim.features import budget
from moim.common.queries import active_members, is_member_active
from moim.common.store import EMPTY, Store

# 예시 자료 S 의 명부 (공통모듈_함수규격.md 2장)
S_MEMBERS = [
    {"name": "양정현", "joined": "2026-09-01", "left": None},
    {"name": "신동훈", "joined": "2026-09-01", "left": "2026-11-30"},
    {"name": "이은경", "joined": "2026-09-01", "left": None},
]


class SCase(StoreCase):
    def setUp(self):
        super().setUp()
        self.store.data["members"] = [dict(m) for m in S_MEMBERS]


class IsMemberActive(SCase):
    """15. is_member_active — 규약 4: 가입일부터 탈퇴일 당일까지 회원."""

    def test_leave_day_is_member(self):
        self.assertIs(is_member_active(self.store, "신동훈", "2026-11-30"), True)

    def test_day_after_leave_is_not_member(self):
        self.assertIs(is_member_active(self.store, "신동훈", "2026-12-01"), False)

    def test_join_day_is_member_day_before_is_not(self):
        self.assertIs(is_member_active(self.store, "양정현", "2026-09-01"), True)
        self.assertIs(is_member_active(self.store, "양정현", "2026-08-31"), False)

    def test_no_leave_date(self):
        self.assertIs(is_member_active(self.store, "이은경", "2030-01-01"), True)

    def test_date_and_datetime_input(self):
        self.assertIs(is_member_active(self.store, "신동훈", dt.date(2026, 11, 30)), True)
        self.assertIs(is_member_active(self.store, "신동훈", dt.datetime(2026, 12, 1, 0, 0)), False)

    def test_unknown_name_or_empty_roster_is_false(self):
        self.assertIs(is_member_active(self.store, "없는사람", "2026-11-17"), False)
        self.store.data["members"] = []
        self.assertIs(is_member_active(self.store, "양정현", "2026-11-17"), False)

    def test_does_not_change_store(self):
        before = [dict(m) for m in self.store.data["members"]]
        is_member_active(self.store, "신동훈", "2026-11-30")
        self.assertEqual(self.store.data["members"], before)

    def test_bad_date_is_error(self):
        for on in ("2026-02-30", "2026.11.17", "", None):
            with self.subTest(on=on), self.assertRaises(ValueError):
                is_member_active(self.store, "양정현", on)

    def test_bad_date_is_error_even_for_unknown_name(self):
        # 형식 오류를 "없는 회원(False)"으로 숨기지 않는다
        with self.assertRaises(ValueError):
            is_member_active(self.store, "없는사람", "2026-02-30")

    def test_bad_name_is_error(self):
        for name in ("", "  ", None, 3):
            with self.subTest(name=name), self.assertRaises(ValueError):
                is_member_active(self.store, name, "2026-11-17")

    def test_bad_roster_dates_are_error(self):
        cases = [
            {"name": "가", "joined": "2026-13-01", "left": None},          # 없는 가입일
            {"name": "가", "joined": None, "left": None},                  # 가입일 없음
            {"name": "가", "joined": "2026-09-01", "left": "2026-11-31"},  # 없는 탈퇴일
            {"name": "가", "joined": "2026-12-01", "left": "2026-11-30"},  # 가입일 > 탈퇴일
        ]
        for m in cases:
            self.store.data["members"] = [m]
            with self.subTest(m=m), self.assertRaises(ValueError):
                is_member_active(self.store, "가", "2026-11-17")


class ActiveMembers(SCase):
    """16. active_members — 그날 회원 이름만, 명부 순서."""

    P = ["양정현", "신동훈", "이은경"]

    def test_all_members(self):
        self.assertEqual(active_members(self.store, "2026-11-17"), self.P)

    def test_leave_day_and_day_after(self):
        self.assertEqual(active_members(self.store, "2026-11-30"), self.P)
        self.assertEqual(active_members(self.store, "2026-12-01"), ["양정현", "이은경"])

    def test_before_anyone_joined(self):
        self.assertEqual(active_members(self.store, "2026-08-31"), [])

    def test_keeps_roster_order(self):
        self.store.data["members"].reverse()
        self.assertEqual(active_members(self.store, "2026-11-17"), ["이은경", "신동훈", "양정현"])

    def test_returns_names_only_and_new_list(self):
        result = active_members(self.store, dt.date(2026, 11, 17))
        self.assertTrue(all(isinstance(n, str) for n in result))
        result.append("바꿈")
        self.assertEqual(active_members(self.store, "2026-11-17"), self.P)

    def test_does_not_change_store(self):
        before = [dict(m) for m in self.store.data["members"]]
        active_members(self.store, "2026-12-01")
        self.assertEqual(self.store.data["members"], before)

    def test_empty_roster(self):
        self.store.data["members"] = []
        self.assertEqual(active_members(self.store, "2026-11-17"), [])

    def test_bad_date_is_error_even_with_empty_roster(self):
        self.store.data["members"] = []
        for on in ("2026-02-30", "", None):
            with self.subTest(on=on), self.assertRaises(ValueError):
                active_members(self.store, on)

    def test_bad_roster_is_error(self):
        cases = [
            "양정현",                                                     # dict 가 아님
            {"joined": "2026-09-01", "left": None},                       # 이름 없음
            {"name": "", "joined": "2026-09-01", "left": None},           # 빈 이름
            {"name": "가", "joined": "2026-12-01", "left": "2026-11-30"},  # 가입일 > 탈퇴일
        ]
        for m in cases:
            self.store.data["members"] = [m]
            with self.subTest(m=m), self.assertRaises(ValueError):
                active_members(self.store, "2026-11-17")

    def test_members_not_a_list_is_error(self):
        self.store.data["members"] = {"양정현": {}}
        with self.assertRaises(ValueError):
            active_members(self.store, "2026-11-17")


class MonthsBetween(unittest.TestCase):
    """17. months_between — 시작 달부터 끝 달까지 양끝 포함, 오름차순."""

    def test_cross_year(self):
        self.assertEqual(months_between((2026, 11), (2027, 1)), [(2026, 11), (2026, 12), (2027, 1)])

    def test_same_month(self):
        self.assertEqual(months_between((2026, 11), (2026, 11)), [(2026, 11)])

    def test_whole_year(self):
        result = months_between((2026, 1), (2026, 12))
        self.assertEqual(result, [(2026, m) for m in range(1, 13)])

    def test_year_range_edges(self):
        self.assertEqual(months_between((1, 1), (1, 2)), [(1, 1), (1, 2)])
        self.assertEqual(months_between((9999, 11), (9999, 12)), [(9999, 11), (9999, 12)])

    def test_does_not_change_input(self):
        start, end = (2026, 11), (2027, 1)
        months_between(start, end)
        self.assertEqual((start, end), ((2026, 11), (2027, 1)))

    def test_start_after_end_is_error(self):
        with self.assertRaises(ValueError):
            months_between((2026, 12), (2026, 11))

    def test_bad_input_is_error(self):
        good = (2026, 11)
        bad_values = [
            "2026-11",       # 문자열은 parse_month 로 바꿔서
            [2026, 11],      # tuple 이 아님
            None,            # 빈 값
            (),              # 길이 0
            (2026,),         # 길이 1
            (2026, 11, 1),   # 길이 3
            (True, 11),      # bool
            (2026, True),
            (2026, 11.0),    # 정수가 아님
            ("2026", 11),
            (0, 11),         # 범위 밖 연도
            (10000, 1),
            (2026, 0),       # 범위 밖 월
            (2026, 13),
        ]
        for bad in bad_values:
            for args in ((bad, good), (good, bad)):
                with self.subTest(args=args), self.assertRaises(ValueError):
                    months_between(*args)


class StorePayments(StoreCase):
    """store.py EMPTY 의 payments 항목(기능 5). 함수규격 '기능 5가 더하는 자료 항목' 표."""

    PAYMENT = {"id": 1, "date": "2026-11-02", "member": "김민수", "amount": 20000,
               "memo": "11월 회비", "source": "manual"}

    def test_new_store_has_empty_payments(self):
        self.assertEqual(Store(self.path("new.json")).data["payments"], [])

    def test_loaded_empty_store_has_empty_payments(self):
        self.assertEqual(self.store.data["payments"], [])

    def test_old_file_without_payments_gets_default(self):
        old = {"members": [], "expenses": [], "next_id": 1}
        with open(self.path("old.json"), "w", encoding="utf-8") as f:
            json.dump(old, f)
        s = Store(self.path("old.json")).load()
        self.assertEqual(s.data["payments"], [])
        self.assertEqual(s.data["next_id"], 1)

    def test_payments_survive_save_and_load(self):
        self.store.data["payments"].append(dict(self.PAYMENT))
        self.store.save()
        s = Store(self.store.path).load()
        self.assertEqual(s.data["payments"], [self.PAYMENT])

    def test_store_does_not_share_empty_payments(self):
        self.store.data["payments"].append(dict(self.PAYMENT))
        self.assertEqual(EMPTY["payments"], [])
        self.assertEqual(Store(self.path("other.json")).data["payments"], [])


class RecordPayment(StoreCase):
    """기본 필수: 회비 입금 기록(누가 언제 얼마). 명부: 김민수·이서연·박지훈(helpers)."""

    def test_record(self):
        p = budget.record_payment(self.store, "2026-11-02", "이서연", "20,000", "11월 회비")
        self.assertEqual(p, {"id": 1, "date": "2026-11-02", "member": "이서연", "amount": 20000,
                             "memo": "11월 회비", "source": "manual"})
        self.assertEqual(self.store.data["payments"], [p])

    def test_ids_increase_from_max(self):
        budget.record_payment(self.store, "2026-11-02", "이서연", 20000)
        self.store.data["payments"][0]["id"] = 7
        self.assertEqual(budget.record_payment(self.store, "2026-11-03", "김민수", 20000)["id"], 8)

    def test_date_and_amount_are_normalized(self):
        p = budget.record_payment(self.store, dt.date(2026, 11, 2), "박지훈", "2.5")
        self.assertEqual((p["date"], p["amount"]), ("2026-11-02", 3))   # 규약 1: 사사오입
        self.assertEqual(budget.record_payment(self.store, "2026-11-02", "박지훈", 2.4)["amount"], 2)

    def test_default_memo_and_source(self):
        p = budget.record_payment(self.store, "2026-11-02", "김민수", 20000)
        self.assertEqual((p["memo"], p["source"]), ("", "manual"))

    def test_returns_copy(self):
        p = budget.record_payment(self.store, "2026-11-02", "김민수", 20000)
        p["amount"] = 1
        self.assertEqual(self.store.data["payments"][0]["amount"], 20000)

    def test_bad_input_is_rejected_and_nothing_saved(self):
        cases = [
            ("2026-11-31", "이서연", 20000, ""),      # 없는 날짜
            ("2026.11.02", "이서연", 20000, ""),      # 형식이 틀린 날짜
            ("2026-11-02", "이서연", 0, ""),          # 0원
            ("2026-11-02", "이서연", -100, ""),       # 음수
            ("2026-11-02", "이서연", "0.4", ""),      # 사사오입하면 0원
            ("2026-11-02", "이서연", "이만원", ""),    # 숫자가 아님
            ("2026-11-02", "이서연", True, ""),       # bool
            ("2026-11-02", "이서연", "inf", ""),      # 무한대
            ("2026-11-02", "없는사람", 20000, ""),    # 명부에 없음
            ("2026-11-02", None, 20000, ""),
            ("2026-11-02", "이서연", 20000, None),    # 메모가 문자열이 아님
        ]
        for date, member, amount, memo in cases:
            with self.subTest(case=(date, member, amount, memo)), self.assertRaises(ValueError):
                budget.record_payment(self.store, date, member, amount, memo)
        self.assertEqual(self.store.data["payments"], [])
        self.assertEqual([m["name"] for m in self.store.data["members"]], NAMES)


class MonthStatus(StoreCase):
    """기본 필수: 월 예산 설정(설정 파일), 이번 달 예산 초과 여부와 남은 금액. 예산은 helpers 의 100,000원."""

    def spend(self, date, amount, deleted=False):
        eid = self.store.new_id()
        self.store.data["expenses"].append(
            {"id": eid, "date": date, "payer": "김민수", "amount": amount, "members": list(NAMES),
             "category": None, "memo": "", "deleted": deleted, "weights": None, "recurring_id": None})

    def status(self, month="2026-11", today=None):
        return budget.month_status(self.store, self.cfg, month, today)

    def test_budget_comes_from_config(self):
        s = self.status()
        self.assertEqual((s["month"], s["budget"], s["spent"]), ("2026-11", 100000, 0))
        self.cfg["budget"]["monthly"] = 1500000
        self.assertEqual(self.status()["budget"], 1500000)

    def test_remaining_and_not_over(self):
        self.spend("2026-11-12", 30000)
        s = self.status()
        self.assertEqual((s["spent"], s["remaining"], s["over"]), (30000, 70000, False))

    def test_exactly_budget_is_not_over(self):
        self.spend("2026-11-12", 100000)
        s = self.status()
        self.assertEqual((s["remaining"], s["over"]), (0, False))

    def test_one_won_over(self):
        self.spend("2026-11-12", 100001)
        s = self.status()
        self.assertEqual((s["remaining"], s["over"]), (-1, True))

    def test_month_includes_first_and_last_day(self):
        # 규약 3: 한 달은 1일부터 말일까지, 양끝 포함
        for date, amount in (("2026-10-31", 1), ("2026-11-01", 20), ("2026-11-30", 300), ("2026-12-01", 4000)):
            self.spend(date, amount)
        self.assertEqual(self.status()["spent"], 320)

    def test_leap_february(self):
        self.spend("2028-02-29", 500)
        self.assertEqual(self.status("2028-02")["spent"], 500)

    def test_deleted_expense_not_counted(self):
        self.spend("2026-11-12", 9000, deleted=True)
        self.assertEqual(self.status()["spent"], 0)

    def test_today_limits_spending(self):
        self.spend("2026-11-10", 1000)
        self.spend("2026-11-20", 2000)
        self.assertEqual(self.status(today="2026-11-10")["spent"], 1000)          # 그날 포함
        self.assertEqual(self.status(today=dt.date(2026, 12, 5))["spent"], 3000)  # 다음 달이면 그달 전체
        self.assertEqual(self.status(today="2026-10-31")["spent"], 0)             # 그달 전이면 0

    def test_does_not_change_store(self):
        self.spend("2026-11-12", 30000)
        before = json.dumps(self.store.data, sort_keys=True)
        self.status(today="2026-11-15")
        self.assertEqual(json.dumps(self.store.data, sort_keys=True), before)

    def test_bad_month_or_today_is_error(self):
        for month in ("2026-13", "2026/11", "", None):
            with self.subTest(month=month), self.assertRaises(ValueError):
                self.status(month)
        with self.assertRaises(ValueError):
            self.status(today="2026-11-31")

    def test_missing_or_bad_budget_is_error(self):
        for cfg in ({}, {"budget": {}}, {"budget": 100000}, {"budget": {"monthly": -1}},
                    {"budget": {"monthly": True}}, {"budget": {"monthly": "100000"}}):
            with self.subTest(cfg=cfg), self.assertRaises(ValueError):
                budget.month_status(self.store, cfg, "2026-11")


class TreasuryBalance(StoreCase):
    """기본 필수: 모임 통장 잔고(입금 합계 − 지출 합계). 명부: 김민수·이서연·박지훈(helpers)."""

    def spend(self, date, amount, deleted=False):
        self.store.data["expenses"].append(
            {"id": self.store.new_id(), "date": date, "payer": "김민수", "amount": amount, "members": list(NAMES),
             "category": None, "memo": "", "deleted": deleted, "weights": None, "recurring_id": None})

    def pay(self, date, member, amount):
        budget.record_payment(self.store, date, member, amount)

    def test_balance(self):
        self.pay("2026-11-02", "김민수", 20000)
        self.spend("2026-11-12", 9000)
        self.assertEqual(budget.treasury_balance(self.store), 11000)

    def test_empty_is_zero(self):
        self.assertEqual(budget.treasury_balance(self.store), 0)

    def test_until_includes_that_day(self):
        self.pay("2026-11-02", "김민수", 20000)
        self.pay("2026-11-20", "이서연", 20000)
        self.spend("2026-11-12", 9000)
        self.spend("2026-11-21", 5000)
        self.assertEqual(budget.treasury_balance(self.store, "2026-11-01"), 0)
        self.assertEqual(budget.treasury_balance(self.store, "2026-11-12"), 11000)          # 11-12 지출 포함
        self.assertEqual(budget.treasury_balance(self.store, dt.date(2026, 11, 20)), 31000)  # 11-20 입금 포함
        self.assertEqual(budget.treasury_balance(self.store), 26000)

    def test_can_be_negative(self):
        self.pay("2026-11-02", "박지훈", 5000)
        self.spend("2026-11-03", 9000)
        self.assertEqual(budget.treasury_balance(self.store), -4000)

    def test_deleted_expense_not_counted(self):
        self.pay("2026-11-02", "김민수", 20000)
        self.spend("2026-11-12", 9000, deleted=True)
        self.assertEqual(budget.treasury_balance(self.store), 20000)

    def test_does_not_change_store(self):
        self.pay("2026-11-02", "김민수", 20000)
        self.spend("2026-11-12", 9000)
        before = json.dumps(self.store.data, sort_keys=True)
        budget.treasury_balance(self.store, "2026-11-30")
        self.assertEqual(json.dumps(self.store.data, sort_keys=True), before)

    def test_bad_until_is_error(self):
        for until in ("2026-11-31", "2026.11.30", ""):
            with self.subTest(until=until), self.assertRaises(ValueError):
                budget.treasury_balance(self.store, until)

    def test_bad_payment_data_is_error(self):
        bad = [
            {"id": 1, "date": "2026-11-31", "member": "김민수", "amount": 100, "memo": "", "source": "manual"},
            {"id": 1, "date": "2026-11-02", "member": "김민수", "amount": 0, "memo": "", "source": "manual"},
            {"id": 1, "date": "2026-11-02", "member": "김민수", "amount": "100", "memo": "", "source": "manual"},
            {"id": 1, "member": "김민수", "amount": 100, "memo": "", "source": "manual"},
            "20000",
        ]
        for p in bad:
            self.store.data["payments"] = [p]
            with self.subTest(p=p), self.assertRaises(ValueError):
                budget.treasury_balance(self.store)


class BudgetCommands(StoreCase):
    """명령 `python -m moim budget status / pay / balance` (moim/commands/budget.py). 예산은 helpers 의 100,000원."""

    def run_cmd(self, argv):
        from moim import cli
        out = []
        args = cli.build_parser().parse_args(argv)
        changed = cli.run(args, self.cfg, self.store, out.append)
        return changed, out

    def spend(self, date, amount):
        self.store.data["expenses"].append(
            {"id": self.store.new_id(), "date": date, "payer": "김민수", "amount": amount, "members": list(NAMES),
             "category": None, "memo": "", "deleted": False, "weights": None, "recurring_id": None})

    def test_status_remaining(self):
        self.spend("2026-11-12", 30000)
        changed, out = self.run_cmd(["budget", "status", "--month", "2026-11"])
        self.assertFalse(changed)   # 조회만 하므로 저장하지 않음
        self.assertEqual(out, ["2026-11 예산 100,000원 / 지출 30,000원", "남은 금액: 70,000원"])

    def test_status_over(self):
        self.spend("2026-11-12", 100001)
        changed, out = self.run_cmd(["budget", "status", "--month", "2026-11"])
        self.assertEqual(out[-1], "예산을 1원 넘었습니다")

    def test_status_defaults_to_this_month(self):
        changed, out = self.run_cmd(["budget", "status"])
        self.assertTrue(out[0].startswith(dates.month_key(dates.today()) + " 예산 100,000원"))

    def test_pay_records_and_saves(self):
        changed, out = self.run_cmd(["budget", "pay", "이서연", "20,000", "--date", "2026-11-02", "--memo", "11월"])
        self.assertTrue(changed)    # 자료를 바꿨으므로 통합 실행 틀이 저장
        self.assertEqual(out, ["회비 입금을 기록했습니다: 1번 2026-11-02 이서연 20,000원"])
        self.assertEqual(self.store.data["payments"][0]["memo"], "11월")

    def test_pay_defaults_to_today(self):
        self.run_cmd(["budget", "pay", "김민수", "20000"])
        self.assertEqual(self.store.data["payments"][0]["date"], dates.fmt(dates.today()))

    def test_balance(self):
        self.run_cmd(["budget", "pay", "김민수", "20000", "--date", "2026-11-02"])
        self.spend("2026-11-12", 9000)
        self.spend("2026-11-20", 5000)
        changed, out = self.run_cmd(["budget", "balance"])
        self.assertFalse(changed)
        self.assertEqual(out, ["모임 통장 잔고: 6,000원"])
        changed, out = self.run_cmd(["budget", "balance", "--until", "2026-11-12"])
        self.assertEqual(out, ["2026-11-12까지 모임 통장 잔고: 11,000원"])

    def test_bad_input_raises_and_nothing_saved(self):
        for argv in (["budget", "pay", "없는사람", "20000", "--date", "2026-11-02"],
                     ["budget", "status", "--month", "2026-13"],
                     ["budget", "balance", "--until", "2026-11-31"]):
            with self.subTest(argv=argv), self.assertRaises(ValueError):
                self.run_cmd(argv)
        self.assertEqual(self.store.data["payments"], [])
