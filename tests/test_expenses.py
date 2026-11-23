"""기능 1 바닥 함수(ledger.validate, ledger.insert) 테스트.

is_member_active(기능 5)·is_locked(기능 4)·check_weights(A1, 기능 4)는 이제 전부
병합돼 있어서 @basic 으로 감싼 테스트도 실제로 돈다(더는 건너뛸 일이 없지만,
혹시 모를 상황을 대비해 데코레이터는 그대로 둔다).
"""

import functools
import unittest

from helpers import NAMES, StoreCase

from moim.common import ledger

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


if __name__ == "__main__":
    unittest.main()
