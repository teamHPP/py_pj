"""기능 5(예산·회비) 테스트. 담당: 김정빈

공통 함수 테스트는 docs/공통모듈_함수규격.md 의 예시 자료 S 명부로 확인한다.
"""

import datetime as dt
import unittest

from helpers import StoreCase

from moim.common.dates import months_between
from moim.common.queries import active_members, is_member_active

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
