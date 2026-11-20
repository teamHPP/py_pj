"""기능 5(예산·회비) 테스트. 담당: 김정빈

공통 함수 테스트는 docs/공통모듈_함수규격.md 의 예시 자료 S 명부로 확인한다.
"""

import datetime as dt

from helpers import StoreCase

from moim.common.queries import is_member_active

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
