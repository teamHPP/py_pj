"""기능 6(가져오기·내보내기) 담당 테스트. 공통 함수 ledger.duplicates 부터.

예시 자료는 docs/공통모듈_함수규격.md 2장의 S 와 같다. 지출은 add_expense 대신 store.data 에 직접 넣는다.
"""

import copy
import datetime as dt
import os
import pathlib
import shutil
import tempfile
import unittest

from helpers import StoreCase

from moim.common import csvio, dates, ledger
from moim.common.queries import period_total, person_paid

P = ["양정현", "신동훈", "이은경"]
E = {
    "id": 1, "date": "2026-11-17", "payer": "양정현", "amount": 9000,
    "members": P, "category": "식비", "memo": "회의 후 저녁",
    "deleted": False, "weights": None, "recurring_id": None,
}


class DuplicatesTest(StoreCase):
    def setUp(self):
        super().setUp()
        self.store.data["members"] = [
            {"name": "양정현", "joined": "2026-09-01", "left": None},
            {"name": "신동훈", "joined": "2026-09-01", "left": "2026-11-30"},
            {"name": "이은경", "joined": "2026-09-01", "left": None},
        ]
        self.store.data["expenses"] = [copy.deepcopy(E)]
        self.store.data["next_id"] = 2

    def add(self, **kw):
        e = copy.deepcopy(E)
        e.update(kw)
        self.store.data["expenses"].append(e)

    # 규격 18절 예시
    def test_spec_examples(self):
        s = self.store
        self.assertEqual(ledger.duplicates(s, "2026-11-17", "양정현", "9,000"), [1])
        self.assertEqual(ledger.duplicates(s, "2026-11-17", "양정현", 9000, exclude_id=1), [])
        self.assertEqual(ledger.duplicates(s, "2026-11-17", "신동훈", 9000), [])
        self.assertEqual(ledger.duplicates(s, "2026-11-17", "양정현", 0), [])

    def test_deleted_excluded(self):
        self.store.data["expenses"][0]["deleted"] = True
        self.assertEqual(ledger.duplicates(self.store, "2026-11-17", "양정현", 9000), [])

    def test_missing_deleted_key_means_not_deleted(self):
        del self.store.data["expenses"][0]["deleted"]
        self.assertEqual(ledger.duplicates(self.store, "2026-11-17", "양정현", 9000), [1])

    def test_sorted_ids_and_exclude(self):
        self.add(id=5)
        self.add(id=3)
        self.add(id=4, date="2026-11-18")
        self.add(id=6, amount=9001)
        s = self.store
        self.assertEqual(ledger.duplicates(s, "2026-11-17", "양정현", 9000), [1, 3, 5])
        self.assertEqual(ledger.duplicates(s, "2026-11-17", "양정현", 9000, exclude_id=3), [1, 5])

    def test_amount_and_date_forms(self):
        s = self.store
        self.assertEqual(ledger.duplicates(s, dt.date(2026, 11, 17), "양정현", "9000원"), [1])
        self.assertEqual(ledger.duplicates(s, dt.datetime(2026, 11, 17, 23, 59), "양정현", 8999.5), [1])
        self.assertEqual(ledger.duplicates(s, "2026-11-17", "양정현", "8999.4"), [])

    def test_empty_and_unknown(self):
        self.assertEqual(ledger.duplicates(self.store, "2026-11-17", "없는사람", 9000), [])
        self.assertEqual(ledger.duplicates(self.store, "2026-11-17", "양정현", -9000), [])
        self.store.data["expenses"] = []
        self.assertEqual(ledger.duplicates(self.store, "2026-11-17", "양정현", 9000), [])

    def test_does_not_change_store(self):
        before = copy.deepcopy(self.store.data)
        ledger.duplicates(self.store, "2026-11-17", "양정현", 9000, exclude_id=1)
        self.assertEqual(self.store.data, before)

    def test_bad_date(self):
        for d in ("2026-02-30", "2026.11.17", "", None):
            with self.assertRaises(ValueError):
                ledger.duplicates(self.store, d, "양정현", 9000)

    def test_bad_amount_message(self):
        for a in ("abc", True, "nan", "inf", "-inf", "1e400", float("nan")):
            with self.assertRaises(ValueError) as cm:
                ledger.duplicates(self.store, "2026-11-17", "양정현", a)
            self.assertIn("금액 형식이 잘못되었습니다", str(cm.exception))

    def test_bad_exclude_id(self):
        for x in (0, -1, True, 1.0, "1"):
            with self.assertRaises(ValueError) as cm:
                ledger.duplicates(self.store, "2026-11-17", "양정현", 9000, exclude_id=x)
            self.assertEqual(str(cm.exception), "제외 번호는 양의 정수여야 합니다")


class MonthKeyTest(unittest.TestCase):
    """20. month_key — 날짜의 달 이름 'YYYY-MM'."""

    # 규격 20절 예시
    def test_spec_examples(self):
        self.assertEqual(dates.month_key("2026-11-17"), "2026-11")
        self.assertEqual(dates.month_key(dt.date(2026, 1, 2)), "2026-01")
        self.assertEqual(dates.month_key(dt.datetime(2026, 11, 30, 23, 59)), "2026-11")

    def test_month_boundaries(self):
        # 한 달은 1일부터 말일까지 — 월초·월말·연말·윤년 2월 29일
        self.assertEqual(dates.month_key("2026-11-01"), "2026-11")
        self.assertEqual(dates.month_key("2026-11-30"), "2026-11")
        self.assertEqual(dates.month_key("2026-12-01"), "2026-12")
        self.assertEqual(dates.month_key("2026-12-31"), "2026-12")
        self.assertEqual(dates.month_key("2028-02-29"), "2028-02")

    def test_bad_values(self):
        for v in ("2026-02-30", "2026-11", "2026.11.17", "2027-02-29", "", None):
            with self.subTest(v=v), self.assertRaises(ValueError):
                dates.month_key(v)



class DetectEncodingTest(unittest.TestCase):
    """21. detect_encoding — UTF-8(BOM 허용) 먼저, 안 되면 CP949."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, name, data):
        path = os.path.join(self.dir, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    # 규격 21절 예시
    def test_spec_examples(self):
        self.assertEqual(csvio.detect_encoding(self.write("u.csv", b"name,amount\nA,9000\n")), "utf-8-sig")
        self.assertEqual(csvio.detect_encoding(self.write("k.csv", "이름,금액\n".encode("cp949"))), "cp949")

    def test_utf8_korean_with_and_without_bom(self):
        text = "거래일자,금액\n2026-11-17,9000\n"
        self.assertEqual(csvio.detect_encoding(self.write("bom.csv", text.encode("utf-8-sig"))), "utf-8-sig")
        self.assertEqual(csvio.detect_encoding(self.write("nobom.csv", text.encode("utf-8"))), "utf-8-sig")

    def test_empty_file(self):
        self.assertEqual(csvio.detect_encoding(self.write("empty.csv", b"")), "utf-8-sig")

    def test_accepts_pathlike(self):
        path = pathlib.Path(self.write("k.csv", "이름\n".encode("cp949")))
        self.assertEqual(csvio.detect_encoding(path), "cp949")

    def test_does_not_change_file(self):
        data = "이름,금액\n".encode("cp949")
        path = self.write("k.csv", data)
        csvio.detect_encoding(path)
        with open(path, "rb") as f:
            self.assertEqual(f.read(), data)

    def test_neither_encoding_is_error(self):
        # 0x80·0xFF 는 UTF-8 로도 CP949 로도 풀 수 없다
        path = self.write("bad.csv", b"name\n\x80\xff\n")
        with self.assertRaises(ValueError) as cm:
            csvio.detect_encoding(path)
        self.assertIn("UTF-8 또는 CP949로 읽을 수 없습니다", str(cm.exception))

    def test_missing_file_is_oserror(self):
        with self.assertRaises(FileNotFoundError):
            csvio.detect_encoding(os.path.join(self.dir, "none.csv"))


class PeriodTotalTest(StoreCase):
    """19. period_total — expenses_in 으로 고른 지출의 금액 합."""

    def setUp(self):
        super().setUp()
        self.store.data["members"] = [
            {"name": "양정현", "joined": "2026-09-01", "left": None},
            {"name": "신동훈", "joined": "2026-09-01", "left": "2026-11-30"},
            {"name": "이은경", "joined": "2026-09-01", "left": None},
        ]
        self.store.data["expenses"] = [copy.deepcopy(E)]
        self.store.data["next_id"] = 2

    def add(self, **kw):
        e = copy.deepcopy(E)
        e.update(kw)
        self.store.data["expenses"].append(e)

    # 규격 19절 예시
    def test_spec_examples(self):
        s = self.store
        self.assertEqual(period_total(s, "2026-11-01", "2026-11-30"), 9000)
        self.assertEqual(period_total(s, "2026-11-17", "2026-11-17"), 9000)
        self.assertEqual(period_total(s, "2026-12-01", "2026-12-31"), 0)
        self.assertEqual(period_total(s, None, None), 9000)
        with self.assertRaises(ValueError):
            period_total(s, "2026-11-30", "2026-11-01")

    def test_deleted_excluded(self):
        self.store.data["expenses"][0]["deleted"] = True
        self.assertEqual(period_total(self.store, "2026-11-01", "2026-11-30"), 0)

    def test_missing_deleted_key_means_not_deleted(self):
        del self.store.data["expenses"][0]["deleted"]
        self.assertEqual(period_total(self.store, "2026-11-01", "2026-11-30"), 9000)

    def test_both_ends_included(self):
        # 기간은 시작일과 끝일을 모두 포함한다(규약 3장) — 월초·월말 지출, 달 밖 지출
        self.add(id=2, date="2026-11-01", amount=1000)
        self.add(id=3, date="2026-11-30", amount=200)
        self.add(id=4, date="2026-10-31", amount=30)
        self.add(id=5, date="2026-12-01", amount=4)
        s = self.store
        self.assertEqual(period_total(s, "2026-11-01", "2026-11-30"), 10200)
        self.assertEqual(period_total(s, None, "2026-11-30"), 10230)
        self.assertEqual(period_total(s, "2026-11-01", None), 10204)
        self.assertEqual(period_total(s, None, None), 10234)

    def test_no_expenses(self):
        self.store.data["expenses"] = []
        self.assertEqual(period_total(self.store, "2026-11-01", "2026-11-30"), 0)
        self.assertEqual(period_total(self.store, None, None), 0)

    def test_returns_int(self):
        total = period_total(self.store, "2026-11-01", "2026-11-30")
        self.assertIs(type(total), int)

    def test_same_as_person_paid_sum(self):
        # 보고서(기능 3)의 사람별 낸 돈 합과 같은 기간 합계가 같아야 한다
        self.add(id=2, date="2026-11-18", amount=3000, payer="이은경")
        self.add(id=3, date="2026-11-19", amount=1234, payer="신동훈", deleted=True)
        s = self.store
        self.assertEqual(period_total(s, "2026-11-01", "2026-11-30"),
                         sum(person_paid(s, "2026-11-01", "2026-11-30").values()))

    def test_does_not_change_store(self):
        before = copy.deepcopy(self.store.data)
        period_total(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(self.store.data, before)

    def test_bad_date(self):
        for d in ("2026-02-30", "2026.11.01"):
            with self.subTest(d=d), self.assertRaises(ValueError):
                period_total(self.store, d, "2026-11-30")


if __name__ == "__main__":
    unittest.main()
