"""기능 1 확장 필수: 참여자 명부 관리(가입일·탈퇴일, 회원 기간 밖 날짜는 참여자 불가)."""

import os
import unittest

from helpers import NAMES, StoreCase

from moim.common import ledger
from moim.features import expenses

KIM, LEE, PARK = NAMES


class AddMember(StoreCase):
    def test_add_creates_member_with_no_leave_date(self):
        m = expenses.add_member(self.store, "최유진", "2026-11-01")
        self.assertEqual((m["name"], m["joined"], m["left"]), ("최유진", "2026-11-01", None))
        self.assertEqual(len(self.store.data["members"]), len(NAMES) + 1)

    def test_rejects_duplicate_name(self):
        with self.assertRaises(ValueError):
            expenses.add_member(self.store, KIM, "2026-11-01")

    def test_rejects_empty_name(self):
        with self.assertRaises(ValueError):
            expenses.add_member(self.store, "  ", "2026-11-01")

    def test_rejects_bad_date(self):
        with self.assertRaises(ValueError):
            expenses.add_member(self.store, "최유진", "2026-02-30")

    def test_new_member_blocks_expense_before_joined(self):
        expenses.add_member(self.store, "최유진", "2026-11-10")
        with self.assertRaises(ValueError):
            ledger.validate(self.store, "2026-11-05", KIM, 9000, ["최유진"])
        d, amt = ledger.validate(self.store, "2026-11-10", KIM, 9000, ["최유진"])
        self.assertEqual((d, amt), ("2026-11-10", 9000))


class LeaveMember(StoreCase):
    def test_leave_sets_left(self):
        m = expenses.leave_member(self.store, KIM, "2026-11-20")
        self.assertEqual(m["left"], "2026-11-20")
        self.assertEqual(self.store.member(KIM)["left"], "2026-11-20")

    def test_rejects_unknown_member(self):
        with self.assertRaises(ValueError):
            expenses.leave_member(self.store, "없는사람", "2026-11-20")

    def test_rejects_left_before_joined(self):
        with self.assertRaises(ValueError):
            expenses.leave_member(self.store, KIM, "2026-08-01")  # joined는 2026-09-01

    def test_rejects_bad_date(self):
        with self.assertRaises(ValueError):
            expenses.leave_member(self.store, KIM, "2026-02-30")

    def test_left_member_blocks_expense_after_left(self):
        expenses.leave_member(self.store, KIM, "2026-11-20")
        d, amt = ledger.validate(self.store, "2026-11-20", LEE, 9000, [KIM])
        self.assertEqual((d, amt), ("2026-11-20", 9000))
        with self.assertRaises(ValueError):
            ledger.validate(self.store, "2026-11-21", LEE, 9000, [KIM])


class ListMembers(StoreCase):
    def test_list_matches_registry_order(self):
        items = expenses.list_members(self.store)
        self.assertEqual([m["name"] for m in items], list(NAMES))

    def test_returns_independent_copies(self):
        items = expenses.list_members(self.store)
        items[0]["left"] = "2026-12-31"
        self.assertIsNone(self.store.member(KIM)["left"])


class LoadMembersFile(StoreCase):
    def write(self, text):
        path = self.path("members.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_adds_new_members(self):
        path = self.write("최유진,2026-11-01\n정하늘,2026-11-02,2026-11-20\n")
        added, left_applied, errors = expenses.load_members_file(self.store, path)
        self.assertEqual(added, ["최유진", "정하늘"])
        self.assertEqual(left_applied, ["정하늘"])
        self.assertEqual(errors, [])
        self.assertEqual(self.store.member("정하늘")["left"], "2026-11-20")
        self.assertIsNone(self.store.member("최유진")["left"])

    def test_existing_member_gets_leave_date_only(self):
        path = self.write(f"{KIM},2026-01-01,2026-11-20\n")
        added, left_applied, errors = expenses.load_members_file(self.store, path)
        self.assertEqual(added, [])
        self.assertEqual(left_applied, [KIM])
        self.assertEqual(errors, [])
        self.assertEqual(self.store.member(KIM)["left"], "2026-11-20")
        self.assertEqual(self.store.member(KIM)["joined"], "2026-09-01")  # 가입일은 안 바뀜

    def test_existing_member_without_leave_date_is_noop(self):
        path = self.write(f"{KIM},2026-01-01\n")
        added, left_applied, errors = expenses.load_members_file(self.store, path)
        self.assertEqual((added, left_applied, errors), ([], [], []))
        self.assertIsNone(self.store.member(KIM)["left"])

    def test_skips_comment_and_blank_lines(self):
        path = self.write("# 주석\n\n최유진,2026-11-01\n")
        added, _, errors = expenses.load_members_file(self.store, path)
        self.assertEqual(added, ["최유진"])
        self.assertEqual(errors, [])

    def test_bad_column_count_reported_with_line_number(self):
        path = self.write("최유진\n")
        added, _, errors = expenses.load_members_file(self.store, path)
        self.assertEqual(added, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][0], 1)

    def test_bad_date_reported_with_line_number_rest_still_applied(self):
        path = self.write("최유진,2026-02-30\n정하늘,2026-11-02\n")
        added, _, errors = expenses.load_members_file(self.store, path)
        self.assertEqual(added, ["정하늘"])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][0], 1)

    def test_leave_before_joined_reported_as_error(self):
        path = self.write("최유진,2026-11-10,2026-11-01\n")
        added, left_applied, errors = expenses.load_members_file(self.store, path)
        self.assertEqual((added, left_applied), ([], []))
        self.assertEqual(len(errors), 1)
        self.assertIsNone(self.store.member("최유진"))


class MemberCommands(StoreCase):
    """moim member add/leave/list 명령이 실제로 연결돼 있는지."""

    def run_cmd(self, argv):
        from moim import cli
        out = []
        args = cli.build_parser().parse_args(argv)
        changed = cli.run(args, self.cfg, self.store, out.append)
        return changed, out

    def test_add_leave_list(self):
        changed, out = self.run_cmd(["member", "add", "최유진", "2026-11-01"])
        self.assertTrue(changed)
        self.assertIn("추가했습니다", out[-1])

        changed, out = self.run_cmd(["member", "leave", "최유진", "2026-11-20"])
        self.assertTrue(changed)
        self.assertIn("탈퇴", out[-1])

        changed, out = self.run_cmd(["member", "list"])
        self.assertFalse(changed)
        self.assertEqual(len(out), len(NAMES) + 1)


if __name__ == "__main__":
    unittest.main()
