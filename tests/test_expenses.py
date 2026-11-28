"""기능 1 바닥 함수(ledger.validate, ledger.insert) 테스트.

is_member_active(기능 5)·is_locked(기능 4)·check_weights(A1, 기능 4)는 이제 전부
병합돼 있어서 @basic 으로 감싼 테스트도 실제로 돈다(더는 건너뛸 일이 없지만,
혹시 모를 상황을 대비해 데코레이터는 그대로 둔다).
"""

import copy
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


class EditExpense(StoreCase):
    """기본 필수: 지출 수정(번호로 지정)."""

    def test_edit_amount(self):
        e, _ = expenses.add_expense(self.store, "2026-11-12", KIM, 3000, NAMES)
        edited = expenses.edit_expense(self.store, e["id"], amount=6000)
        self.assertEqual(edited["amount"], 6000)
        self.assertEqual(self.store.get_expense(e["id"])["amount"], 6000)

    def test_records_history_with_before_after(self):
        e, _ = expenses.add_expense(self.store, "2026-11-12", KIM, 3000, NAMES)
        expenses.edit_expense(self.store, e["id"], amount=6000)
        last = self.store.data["history"][-1]
        self.assertEqual((last["action"], last["before"]["amount"], last["after"]["amount"]),
                          ("edit", 3000, 6000))

    def test_rejects_unknown_field(self):
        e, _ = expenses.add_expense(self.store, "2026-11-12", KIM, 3000, NAMES)
        with self.assertRaises(ValueError):
            expenses.edit_expense(self.store, e["id"], id=999)

    def test_rejects_editing_deleted(self):
        e, _ = expenses.add_expense(self.store, "2026-11-12", KIM, 3000, NAMES)
        expenses.delete_expense(self.store, e["id"])
        with self.assertRaises(ValueError):
            expenses.edit_expense(self.store, e["id"], amount=1)

    def test_rejects_when_old_date_locked(self):
        e, _ = expenses.add_expense(self.store, "2026-11-12", KIM, 3000, NAMES)
        self.store.data["locks"] = [{"start": "2026-11-01", "end": "2026-11-30"}]
        with self.assertRaises(ValueError):
            expenses.edit_expense(self.store, e["id"], amount=6000)

    def test_rejects_moving_into_locked_period(self):
        e, _ = expenses.add_expense(self.store, "2026-10-12", KIM, 3000, NAMES)
        self.store.data["locks"] = [{"start": "2026-11-01", "end": "2026-11-30"}]
        with self.assertRaises(ValueError):
            expenses.edit_expense(self.store, e["id"], date="2026-11-12")

    def test_failed_edit_leaves_store_unchanged(self):
        e, _ = expenses.add_expense(self.store, "2026-11-12", KIM, 3000, NAMES)
        before = copy.deepcopy(self.store.data)
        with self.assertRaises(ValueError):
            expenses.edit_expense(self.store, e["id"], amount=-1)
        self.assertEqual(self.store.data, before)


class DeleteExpense(StoreCase):
    """기본 필수: 지출 삭제(지우지 않고 표시만)."""

    def test_marks_not_removes(self):
        e, _ = expenses.add_expense(self.store, "2026-11-12", KIM, 3000, NAMES)
        expenses.delete_expense(self.store, e["id"])
        self.assertEqual(len(self.store.data["expenses"]), 1)
        self.assertTrue(self.store.get_expense(e["id"])["deleted"])

    def test_rejects_double_delete(self):
        e, _ = expenses.add_expense(self.store, "2026-11-12", KIM, 3000, NAMES)
        expenses.delete_expense(self.store, e["id"])
        with self.assertRaises(ValueError):
            expenses.delete_expense(self.store, e["id"])

    def test_rejects_locked_delete(self):
        e, _ = expenses.add_expense(self.store, "2026-11-12", KIM, 3000, NAMES)
        self.store.data["locks"] = [{"start": "2026-11-01", "end": "2026-11-30"}]
        with self.assertRaises(ValueError):
            expenses.delete_expense(self.store, e["id"])


class HistoryQuery(StoreCase):
    """확장 필수: 수정·삭제 이력 조회. 기록(store.record)은 이미 merge된 상태."""

    def test_returns_all_in_order(self):
        a, _ = expenses.add_expense(self.store, "2026-11-12", KIM, 3000, NAMES)
        b, _ = expenses.add_expense(self.store, "2026-11-13", LEE, 4000, NAMES)
        expenses.edit_expense(self.store, a["id"], amount=5000)
        items = expenses.history(self.store)
        self.assertEqual([(h["action"], h["id"]) for h in items],
                          [("add", a["id"]), ("add", b["id"]), ("edit", a["id"])])

    def test_filters_by_id(self):
        a, _ = expenses.add_expense(self.store, "2026-11-12", KIM, 3000, NAMES)
        b, _ = expenses.add_expense(self.store, "2026-11-13", LEE, 4000, NAMES)
        expenses.edit_expense(self.store, a["id"], amount=5000)
        items = expenses.history(self.store, a["id"])
        self.assertEqual([h["action"] for h in items], ["add", "edit"])
        self.assertTrue(all(h["id"] == a["id"] for h in items))
        self.assertEqual(expenses.history(self.store, b["id"]), [h for h in expenses.history(self.store)
                                                                   if h["id"] == b["id"]])

    def test_no_history_for_unknown_id(self):
        expenses.add_expense(self.store, "2026-11-12", KIM, 3000, NAMES)
        self.assertEqual(expenses.history(self.store, 999), [])

    def test_returns_independent_copies(self):
        e, _ = expenses.add_expense(self.store, "2026-11-12", KIM, 3000, NAMES)
        items = expenses.history(self.store)
        items[0]["action"] = "손상"
        self.assertEqual(self.store.data["history"][0]["action"], "add")


class AddFromFile(StoreCase):
    """확장 필수: 여러 줄 한꺼번에 입력(파일에서 읽기), 잘못된 줄은 줄 번호+이유 보고."""

    def write(self, text):
        path = self.path("bulk.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return path

    def test_adds_valid_lines(self):
        path = self.write(f"2026-11-12,{KIM},9000,{KIM};{LEE},회의 후 저녁\n"
                           f"2026-11-13,{LEE},3000,{LEE}\n")
        added, errors = expenses.add_from_file(self.store, path)
        self.assertEqual(len(added), 2)
        self.assertEqual(errors, [])
        self.assertEqual(self.store.get_expense(added[0])["memo"], "회의 후 저녁")
        self.assertEqual(self.store.get_expense(added[1])["memo"], "")

    def test_history_action_is_file_import(self):
        # 함수 규격 A2: add_from_file은 이력에 "file_import"로 남아야 한다
        path = self.write(f"2026-11-12,{KIM},9000,{KIM}\n")
        expenses.add_from_file(self.store, path)
        self.assertEqual([h["action"] for h in self.store.data["history"]], ["file_import"])

    def test_skips_comment_and_blank_lines(self):
        path = self.write(f"# 주석\n\n2026-11-12,{KIM},9000,{KIM}\n")
        added, errors = expenses.add_from_file(self.store, path)
        self.assertEqual(len(added), 1)
        self.assertEqual(errors, [])

    def test_memo_with_comma_needs_quotes(self):
        path = self.write(f'2026-11-12,{KIM},9000,{KIM},"메모, 쉼표 포함"\n')
        added, errors = expenses.add_from_file(self.store, path)
        self.assertEqual(errors, [])
        self.assertEqual(self.store.get_expense(added[0])["memo"], "메모, 쉼표 포함")

    def test_bad_column_count_reported_with_line_number(self):
        path = self.write(f"2026-11-12,{KIM},9000\n")
        added, errors = expenses.add_from_file(self.store, path)
        self.assertEqual(added, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][0], 1)

    def test_bad_row_skipped_rest_still_added(self):
        path = self.write(f"2026-11-12,{KIM},0,{KIM}\n"             # 0원 거부
                           f"2026-11-13,{LEE},3000,{LEE}\n"          # 정상
                           f"2026-11-14,없는사람,1000,{KIM}\n")      # 명부에 없는 사람
        added, errors = expenses.add_from_file(self.store, path)
        self.assertEqual(len(added), 1)
        self.assertEqual([n for n, _ in errors], [1, 3])
        self.assertEqual(len(self.store.data["expenses"]), 1)

    def test_members_separated_by_semicolon(self):
        path = self.write(f"2026-11-12,{KIM},9000,{KIM};{LEE};{PARK}\n")
        added, _ = expenses.add_from_file(self.store, path)
        self.assertEqual(self.store.get_expense(added[0])["members"], [KIM, LEE, PARK])

    def test_missing_file_raises_oserror(self):
        with self.assertRaises(OSError):
            expenses.add_from_file(self.store, self.path("없음.csv"))

    def test_cp949_file_is_detected(self):
        path = self.path("bulk_cp949.csv")
        with open(path, "w", encoding="cp949", newline="") as f:
            f.write(f"2026-11-12,{KIM},9000,{KIM},메모\n")
        added, errors = expenses.add_from_file(self.store, path)
        self.assertEqual(errors, [])
        self.assertEqual(self.store.get_expense(added[0])["memo"], "메모")

    def test_quoted_newline_keeps_real_line_number(self):
        # 따옴표 안 줄바꿈이 있는 줄은 2개의 실제 줄을 차지하므로, 그다음 줄의 줄 번호가 밀리면 안 된다
        path = self.path("bulk.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(f'2026-11-12,{KIM},9000,{KIM},"메모\n줄바꿈"\n2026-13-01,{KIM},1000,{KIM}\n')
        added, errors = expenses.add_from_file(self.store, path)
        self.assertEqual(len(added), 1)
        self.assertEqual(self.store.get_expense(added[0])["memo"], "메모\n줄바꿈")
        self.assertEqual(errors[0][0], 3)  # 첫 줄이 2개 줄을 차지했으므로 오류 줄은 3번째 실제 줄


class ExpenseCommands(StoreCase):
    """moim exp add/list/edit/delete 명령이 실제로 연결돼 있는지."""

    def run_cmd(self, argv):
        from moim import cli
        out = []
        args = cli.build_parser().parse_args(argv)
        changed = cli.run(args, self.cfg, self.store, out.append)
        return changed, out

    def test_add_list_edit_delete(self):
        changed, out = self.run_cmd(["exp", "add", "2026-11-12", KIM, "9,000", f"{KIM};{LEE}",
                                      "--memo", "회의 후 저녁"])
        self.assertTrue(changed)
        self.assertIn("추가했습니다", out[-1])
        eid = self.store.data["expenses"][0]["id"]

        changed, out = self.run_cmd(["exp", "list"])
        self.assertFalse(changed)
        self.assertEqual(len(out), 1)

        changed, out = self.run_cmd(["exp", "edit", str(eid), "--amount", "6000"])
        self.assertTrue(changed)
        self.assertEqual(self.store.get_expense(eid)["amount"], 6000)

        changed, out = self.run_cmd(["exp", "delete", str(eid)])
        self.assertTrue(changed)
        self.assertTrue(self.store.get_expense(eid)["deleted"])

    def test_history(self):
        changed, out = self.run_cmd(["exp", "add", "2026-11-12", KIM, "9,000", f"{KIM};{LEE}"])
        self.assertTrue(changed)
        eid = self.store.data["expenses"][0]["id"]
        self.run_cmd(["exp", "edit", str(eid), "--amount", "6000"])

        changed, out = self.run_cmd(["exp", "history"])
        self.assertFalse(changed)
        self.assertEqual(len(out), 2)

        changed, out = self.run_cmd(["exp", "history", str(eid)])
        self.assertEqual(len(out), 2)

    def test_import_lines(self):
        path = self.path("bulk.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(f"2026-11-12,{KIM},9000,{KIM}\n2026-13-01,{KIM},1000,{KIM}\n")
        changed, out = self.run_cmd(["exp", "import-lines", path])
        self.assertTrue(changed)
        self.assertIn("추가했습니다: 1건", out[0])
        self.assertTrue(out[1].startswith("오류 2번 줄: "))


if __name__ == "__main__":
    unittest.main()
