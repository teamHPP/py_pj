"""기능 4(정산) 담당의 테스트. 공통 함수 queries.is_locked 의 규격(docs/공통모듈_함수규격.md 12절)을 확인한다."""

import copy
import datetime as dt
import json
import unittest

from helpers import StoreCase

from moim.common.queries import is_locked
from moim.common.store import EMPTY, Store

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


if __name__ == "__main__":
    unittest.main()
