"""기능 1 바닥 함수(ledger.validate, ledger.insert) 테스트.

is_member_active(기능 5)·is_locked(기능 4)·check_weights(A1, 기능 4)는 이제 전부
병합돼 있어서 @basic 으로 감싼 테스트도 실제로 돈다(더는 건너뛸 일이 없지만,
혹시 모를 상황을 대비해 데코레이터는 그대로 둔다).
"""

import functools
import unittest

from helpers import NAMES, StoreCase

from moim.common import ledger
from moim.features import expenses

KIM, LEE, PARK = NAMES


def basic(fn):
    @functools.wraps(fn)
    def wrapper(self):
        try:
            fn(self)
        except NotImplementedError as exc:
            self.skipTest(f"아직 구현 전: {exc}")
    return wrapper


class ValidateFormatChecks(StoreCase):
    """is_member_active·is_locked 를 거치기 전에 걸러지는 입력 형식 검사."""

    def test_rejects_zero_amount(self):
        with self.assertRaises(ValueError):
            ledger.validate(self.store, "2026-11-12", KIM, 0, NAMES)

    def test_rejects_negative_amount(self):
        with self.assertRaises(ValueError):
            ledger.validate(self.store, "2026-11-12", KIM, -3000, NAMES)

    def test_rejects_bool_amount(self):
        with self.assertRaises(ValueError):
            ledger.validate(self.store, "2026-11-12", KIM, True, NAMES)

    def test_rejects_inf_amount(self):
        with self.assertRaises(ValueError):
            ledger.validate(self.store, "2026-11-12", KIM, "inf", NAMES)

    def test_rejects_nan_amount(self):
        with self.assertRaises(ValueError):
            ledger.validate(self.store, "2026-11-12", KIM, "nan", NAMES)

    def test_rejects_bad_date(self):
        with self.assertRaises(ValueError):
            ledger.validate(self.store, "2026-02-30", KIM, 9000, NAMES)

    def test_rejects_empty_members(self):
        with self.assertRaises(ValueError):
            ledger.validate(self.store, "2026-11-12", KIM, 9000, [])

    def test_rejects_duplicate_members(self):
        with self.assertRaises(ValueError):
            ledger.validate(self.store, "2026-11-12", KIM, 9000, [KIM, KIM, LEE])

    def test_rejects_weights_for_non_participant(self):
        # money.check_weights(A1)가 검사 — 참여자 목록(members)만 보고 거부, 명부는 안 본다.
        with self.assertRaises(ValueError):
            ledger.validate(self.store, "2026-11-12", KIM, 9000, NAMES, weights={"없는사람": 1})

    def test_rejects_bad_weight_ratio(self):
        with self.assertRaises(ValueError):
            ledger.validate(self.store, "2026-11-12", KIM, 9000, NAMES, weights={KIM: 0})


class ValidateAndInsertWithMembership(StoreCase):
    """is_member_active(기능 5)·is_locked(기능 4)가 있어야 끝까지 도는 부분."""

    @basic
    def test_validate_success(self):
        d, amt = ledger.validate(self.store, "2026-11-12", KIM, "9,000", NAMES)
        self.assertEqual((d, amt), ("2026-11-12", 9000))

    @basic
    def test_validate_rounds_amount(self):
        _, amt = ledger.validate(self.store, "2026-11-12", KIM, "2.5", NAMES)
        self.assertEqual(amt, 3)

    @basic
    def test_validate_rejects_non_member(self):
        with self.assertRaises(ValueError):
            ledger.validate(self.store, "2026-11-12", KIM, 9000, ["없는사람"])

    @basic
    def test_insert_creates_expense(self):
        e = ledger.insert(self.store, "2026-11-12", KIM, 9000, NAMES, memo="회의 후 저녁", category="식비")
        self.assertEqual((e["amount"], e["members"], e["memo"], e["category"], e["deleted"]),
                         (9000, NAMES, "회의 후 저녁", "식비", False))
        self.assertEqual(self.store.data["next_id"], e["id"] + 1)

    @basic
    def test_insert_records_history(self):
        e = ledger.insert(self.store, "2026-11-12", KIM, 9000, NAMES)
        last = self.store.data["history"][-1]
        self.assertEqual((last["action"], last["id"], last["before"], last["after"]["id"]),
                          ("add", e["id"], None, e["id"]))

    @basic
    def test_insert_rejects_bad_action(self):
        with self.assertRaises(ValueError):
            ledger.insert(self.store, "2026-11-12", KIM, 9000, NAMES, action="이상한값")

    @basic
    def test_insert_does_not_bump_id_on_failure(self):
        next_id = self.store.data["next_id"]
        with self.assertRaises(ValueError):
            ledger.insert(self.store, "2026-11-12", KIM, 9000, NAMES, action="이상한값")
        self.assertEqual(self.store.data["next_id"], next_id)

    @basic
    def test_validate_accepts_weights(self):
        d, amt = ledger.validate(self.store, "2026-11-12", KIM, 10001, NAMES, weights={KIM: 2})
        self.assertEqual((d, amt), ("2026-11-12", 10001))

    @basic
    def test_insert_stores_raw_weights(self):
        # insert 는 weights 를 받은 그대로 저장한다(정규화는 쓰는 쪽(expense_shares)이 할 때 한다).
        e = ledger.insert(self.store, "2026-11-12", KIM, 10001, NAMES, weights={KIM: 2})
        self.assertEqual(e["weights"], {KIM: 2})


class AddExpense(StoreCase):
    """기본 필수: 지출 추가. ledger.insert 를 거치고, 중복은 경고만(거부 아님)."""

    def test_no_warning_when_not_duplicate(self):
        e, warnings = expenses.add_expense(self.store, "2026-11-12", KIM, 9000, NAMES)
        self.assertEqual(warnings, [])
        self.assertEqual(e["amount"], 9000)

    def test_warns_on_duplicate(self):
        first, _ = expenses.add_expense(self.store, "2026-11-12", KIM, 9000, NAMES)
        _, warnings = expenses.add_expense(self.store, "2026-11-12", KIM, 9000, NAMES)
        self.assertEqual(len(warnings), 1)
        self.assertIn(str(first["id"]), warnings[0])

    def test_duplicate_is_still_added(self):
        expenses.add_expense(self.store, "2026-11-12", KIM, 9000, NAMES)
        expenses.add_expense(self.store, "2026-11-12", KIM, 9000, NAMES)
        self.assertEqual(len(self.store.data["expenses"]), 2)

    def test_rejects_locked_date(self):
        self.store.data["locks"] = [{"start": "2026-11-01", "end": "2026-11-30"}]
        with self.assertRaises(ValueError):
            expenses.add_expense(self.store, "2026-11-12", KIM, 9000, NAMES)


class ListExpenses(StoreCase):
    """기본 필수: 지출 목록(번호순·날짜순)."""

    def test_excludes_deleted_by_default(self):
        kept, _ = expenses.add_expense(self.store, "2026-11-13", KIM, 3000, NAMES)
        removed, _ = expenses.add_expense(self.store, "2026-11-12", KIM, 9000, NAMES)
        self.store.get_expense(removed["id"])["deleted"] = True
        self.assertEqual([e["id"] for e in expenses.list_expenses(self.store)], [kept["id"]])

    def test_include_deleted(self):
        e, _ = expenses.add_expense(self.store, "2026-11-12", KIM, 9000, NAMES)
        self.store.get_expense(e["id"])["deleted"] = True
        ids = [x["id"] for x in expenses.list_expenses(self.store, include_deleted=True)]
        self.assertEqual(ids, [e["id"]])

    def test_order_date_then_id(self):
        a, _ = expenses.add_expense(self.store, "2026-11-20", KIM, 3000, NAMES)
        b, _ = expenses.add_expense(self.store, "2026-11-05", KIM, 6000, NAMES)
        ids = [e["id"] for e in expenses.list_expenses(self.store, order="date")]
        self.assertEqual(ids, [b["id"], a["id"]])

    def test_rejects_bad_order(self):
        with self.assertRaises(ValueError):
            expenses.list_expenses(self.store, order="amount")

    def test_returns_independent_copies(self):
        e, _ = expenses.add_expense(self.store, "2026-11-12", KIM, 9000, NAMES)
        got = expenses.list_expenses(self.store)
        got[0]["amount"] = 1
        self.assertEqual(self.store.get_expense(e["id"])["amount"], 9000)


class ExpenseCommands(StoreCase):
    """moim exp add/list 명령이 실제로 연결돼 있는지."""

    def run_cmd(self, argv):
        from moim import cli
        out = []
        args = cli.build_parser().parse_args(argv)
        changed = cli.run(args, self.cfg, self.store, out.append)
        return changed, out

    def test_add_list(self):
        changed, out = self.run_cmd(["exp", "add", "2026-11-12", KIM, "9,000", f"{KIM};{LEE}",
                                      "--memo", "회의 후 저녁"])
        self.assertTrue(changed)
        self.assertIn("추가했습니다", out[-1])

        changed, out = self.run_cmd(["exp", "list"])
        self.assertFalse(changed)
        self.assertEqual(len(out), 1)


if __name__ == "__main__":
    unittest.main()
