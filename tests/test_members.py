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

    def test_rejects_leave_date_before_existing_expense_as_participant(self):
        expenses.add_expense(self.store, "2026-11-20", LEE, 9000, [KIM, LEE])
        with self.assertRaises(ValueError):
            expenses.leave_member(self.store, KIM, "2026-11-10")
        self.assertIsNone(self.store.member(KIM)["left"])  # 거부되면 아무것도 안 바뀐다

    def test_rejects_leave_date_before_existing_expense_as_payer(self):
        expenses.add_expense(self.store, "2026-11-20", KIM, 9000, [LEE])
        with self.assertRaises(ValueError):
            expenses.leave_member(self.store, KIM, "2026-11-10")

    def test_allows_leave_date_when_later_expense_is_deleted(self):
        e, _ = expenses.add_expense(self.store, "2026-11-20", LEE, 9000, [KIM, LEE])
        expenses.delete_expense(self.store, e["id"])
        m = expenses.leave_member(self.store, KIM, "2026-11-10")
        self.assertEqual(m["left"], "2026-11-10")

    def test_allows_leave_date_on_the_expense_date_itself(self):
        expenses.add_expense(self.store, "2026-11-20", LEE, 9000, [KIM, LEE])
        m = expenses.leave_member(self.store, KIM, "2026-11-20")
        self.assertEqual(m["left"], "2026-11-20")


class ListMembers(StoreCase):
    def test_list_matches_registry_order(self):
        items = expenses.list_members(self.store)
        self.assertEqual([m["name"] for m in items], list(NAMES))

    def test_returns_independent_copies(self):
        items = expenses.list_members(self.store)
        items[0]["left"] = "2026-12-31"
        self.assertIsNone(self.store.member(KIM)["left"])


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
