"""기능 1 바닥 함수(ledger.validate, ledger.insert) 테스트.

is_member_active(기능 5)·is_locked(기능 4)는 아직 구현 전이라, 그 둘을 실제로
거쳐야 하는 테스트는 @basic 으로 감싸 "아직 구현 전"이면 건너뛴다(에러 아님).
금액·날짜·참여자 형식 검사처럼 그 둘을 거치지 않고도 확인되는 부분은 바로 돈다.
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

    def test_weights_not_ready_yet(self):
        # A1 money.check_weights(기능 4, 2단계)가 아직 없어서 당분간 거부한다.
        with self.assertRaises(NotImplementedError):
            ledger.validate(self.store, "2026-11-12", KIM, 9000, NAMES, weights={KIM: 2})


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


if __name__ == "__main__":
    unittest.main()
