"""기능 6(가져오기·내보내기) 담당 테스트. 공통 함수 ledger.duplicates 부터.

예시 자료는 docs/공통모듈_함수규격.md 2장의 S 와 같다. 지출은 add_expense 대신 store.data 에 직접 넣는다.
"""

import copy
import csv
import datetime as dt
import json
import os
import pathlib
import shutil
import tempfile
import unittest

from helpers import StoreCase

from moim.common import csvio, dates, ledger
from moim.common.queries import period_total, person_paid
from moim.features import transfer_io

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


class ReadCsvRowsTest(unittest.TestCase):
    """22. read_csv_rows — CSV 읽기와 열 이름 연결."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, data, name="t.csv"):
        path = os.path.join(self.dir, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    # 규격 22절 예시
    def test_spec_example(self):
        path = self.write('거래일자,금액\n\n2026-11-17,"9,000"\n2026-11-18\n'.encode("utf-8"), "b.csv")
        got = csvio.read_csv_rows(path, {"날짜": "date", "거래일자": "date", "금액": "amount"})
        self.assertEqual(got, ("utf-8-sig", [
            (3, {"date": "2026-11-17", "amount": "9,000"}),
            (4, {"date": "2026-11-18", "amount": None}),
        ]))

    def test_bom_does_not_break_first_header(self):
        path = self.write("거래일자,금액\n2026-11-17,9000\n".encode("utf-8-sig"))
        self.assertEqual(csvio.read_csv_rows(path),
                         ("utf-8-sig", [(2, {"거래일자": "2026-11-17", "금액": "9000"})]))

    def test_cp949_detected(self):
        path = self.write("거래일자,금액\n2026-11-17,9000\n".encode("cp949"))
        self.assertEqual(csvio.read_csv_rows(path),
                         ("cp949", [(2, {"거래일자": "2026-11-17", "금액": "9000"})]))

    def test_given_encoding(self):
        utf8 = self.write("이름\n가\n".encode("utf-8-sig"), "u.csv")
        cp949 = self.write("이름\n가\n".encode("cp949"), "k.csv")
        for enc in ("utf-8", "utf-8-sig"):
            with self.subTest(enc=enc):
                self.assertEqual(csvio.read_csv_rows(utf8, encoding=enc), ("utf-8-sig", [(2, {"이름": "가"})]))
        self.assertEqual(csvio.read_csv_rows(cp949, encoding="cp949"), ("cp949", [(2, {"이름": "가"})]))

    def test_unsupported_encoding(self):
        path = self.write(b"a\n1\n")
        for enc in ("euc-kr", "latin-1", "UTF8", ""):
            with self.subTest(enc=enc), self.assertRaises(ValueError):
                csvio.read_csv_rows(path, encoding=enc)

    def test_given_encoding_cannot_decode(self):
        path = self.write("이름\n가\n".encode("utf-8"))
        with self.assertRaises(ValueError):
            csvio.read_csv_rows(path, encoding="cp949")

    def test_mapping_not_dict(self):
        path = self.write(b"a\n1\n")
        for m in (["a"], "a", 1):
            with self.subTest(m=m), self.assertRaises(ValueError):
                csvio.read_csv_rows(path, m)

    def test_mapping_keeps_unmapped_and_ignores_missing_keys(self):
        path = self.write("거래일자,적요,금액\n2026-11-17,저녁,9000\n".encode("utf-8"))
        got = csvio.read_csv_rows(path, {"날짜": "date", "거래일자": "date", "메모": "memo"})
        self.assertEqual(got[1], [(2, {"date": "2026-11-17", "적요": "저녁", "금액": "9000"})])

    def test_header_stripped_values_unchanged(self):
        path = self.write(' 거래일자 , 금액 \n 2026-11-17 ," 9,000 "\n'.encode("utf-8"))
        self.assertEqual(csvio.read_csv_rows(path)[1], [(2, {"거래일자": " 2026-11-17 ", "금액": " 9,000 "})])

    def test_quoted_newline_uses_start_line(self):
        path = self.write(b'a,b\n1,"x\ny"\n2,z\n')
        self.assertEqual(csvio.read_csv_rows(path)[1], [(2, {"a": "1", "b": "x\ny"}), (4, {"a": "2", "b": "z"})])

    def test_crlf_and_blank_lines(self):
        path = self.write(b"a,b\r\n1,2\r\n\r\n\r\n3,4\r\n")
        self.assertEqual(csvio.read_csv_rows(path)[1], [(2, {"a": "1", "b": "2"}), (5, {"a": "3", "b": "4"})])

    def test_extra_values_go_to_none_key(self):
        path = self.write(b"a,b\n1,2,3,4\n")
        self.assertEqual(csvio.read_csv_rows(path)[1], [(2, {"a": "1", "b": "2", None: ["3", "4"]})])

    def test_spaces_only_line_is_a_short_row(self):
        # csv.DictReader 처럼 완전히 빈 줄만 건너뛴다. 공백뿐인 줄은 열이 모자란 행 → 부르는 쪽이 오류로 보고
        path = self.write(b"a,b\n   \n")
        self.assertEqual(csvio.read_csv_rows(path)[1], [(2, {"a": "   ", "b": None})])

    def test_empty_and_header_only(self):
        for data in (b"", b"\xef\xbb\xbf", b"a,b\n", b"a,b\n\n\n"):
            with self.subTest(data=data):
                self.assertEqual(csvio.read_csv_rows(self.write(data)), ("utf-8-sig", []))

    def test_bad_header(self):
        for data in (b"a,,b\n1,2,3\n", b"a, \n1,2\n", b"a,a\n1,2\n", b" a,a \n1,2\n", b"\na,b\n1,2\n"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                csvio.read_csv_rows(self.write(data))

    def test_two_columns_same_field(self):
        both = self.write("날짜,거래일자\n1,2\n".encode("utf-8"), "both.csv")
        with self.assertRaises(ValueError):
            csvio.read_csv_rows(both, {"날짜": "date", "거래일자": "date"})
        clash = self.write("date,거래일자\n1,2\n".encode("utf-8"), "clash.csv")
        with self.assertRaises(ValueError):
            csvio.read_csv_rows(clash, {"거래일자": "date"})

    def test_neither_encoding(self):
        with self.assertRaises(ValueError):
            csvio.read_csv_rows(self.write(b"a\n\x80\xff\n"))

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            csvio.read_csv_rows(os.path.join(self.dir, "none.csv"))

    def test_bank_format_example(self):
        # docs/은행거래내역형식.md 의 예(CP949), 기능 5가 쓰는 방식
        text = ("거래일자,거래시각,적요,출금액,입금액,잔액\n"
                "2026.11.01,09:10,이서연,,20000,20000\n"
                '2026.11.03,19:42,회의 후 저녁,"48,000",,-28000\n')
        path = self.write(text.encode("cp949"), "bank.csv")
        enc, rows = csvio.read_csv_rows(path, {"거래일자": "date", "적요": "memo"})
        self.assertEqual(enc, "cp949")
        self.assertEqual([n for n, _ in rows], [2, 3])
        self.assertEqual(rows[1][1], {"date": "2026.11.03", "거래시각": "19:42", "memo": "회의 후 저녁",
                                      "출금액": "48,000", "입금액": "", "잔액": "-28000"})


class ExportData(StoreCase):
    """내보내기 테스트 공용 자료: 삭제 제외 4건 17,000원(10월 1건, 11월 2건, 12월 1건)."""

    def setUp(self):
        super().setUp()
        rows = [
            dict(id=1, date="2026-10-31", payer="양정현", amount=3000, category="식비"),
            dict(id=2, date="2026-11-01", payer="이은경", amount=6000, category="교통",
                 weights={"양정현": 2, "이은경": 1}),
            dict(id=3, date="2026-11-30", payer="신동훈", amount=1000, category=None, memo=""),
            dict(id=4, date="2026-11-15", payer="양정현", amount=5000, category="식비", deleted=True),
            dict(id=5, date="2026-12-01", payer="양정현", amount=7000, category=" 식비 "),
        ]
        self.store.data["expenses"] = []
        for r in rows:
            e = copy.deepcopy(E)
            e.update(r)
            self.store.data["expenses"].append(e)
        self.store.data["next_id"] = 6


class ExportTest(ExportData):
    """export_csv · export_json: 기간·분류 고르기, 삭제 제외, 파일 형식."""

    def read_csv(self, path):
        with open(path, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def test_csv_all_excludes_deleted(self):
        p = self.path("a.csv")
        self.assertEqual(transfer_io.export_csv(self.store, p), (4, 17000))
        rows = self.read_csv(p)
        self.assertEqual([r["id"] for r in rows], ["1", "2", "3", "5"])
        self.assertEqual(list(rows[0]), transfer_io.CSV_FIELDS)

    def test_csv_has_bom_and_korean(self):
        p = self.path("a.csv")
        transfer_io.export_csv(self.store, p)
        with open(p, "rb") as f:
            raw = f.read()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertIn("회의 후 저녁".encode("utf-8"), raw)
        self.assertEqual(csvio.detect_encoding(p), "utf-8-sig")

    def test_csv_field_formats(self):
        p = self.path("a.csv")
        transfer_io.export_csv(self.store, p)
        rows = {r["id"]: r for r in self.read_csv(p)}
        self.assertEqual(rows["2"]["members"], "양정현;신동훈;이은경")
        self.assertEqual(rows["2"]["weights"], "양정현=2;이은경=1")
        self.assertEqual(rows["1"]["weights"], "")
        self.assertEqual(rows["3"]["category"], "")
        self.assertEqual(rows["1"]["amount"], "3000")

    def test_period_both_ends_included(self):
        p = self.path("a.csv")
        self.assertEqual(transfer_io.export_csv(self.store, p, "2026-11-01", "2026-11-30"), (2, 7000))
        self.assertEqual(transfer_io.export_json(self.store, p, start="2026-11-01"), (3, 14000))
        self.assertEqual(transfer_io.export_json(self.store, p, end="2026-11-01"), (2, 9000))

    def test_category(self):
        p = self.path("a.csv")
        self.assertEqual(transfer_io.export_csv(self.store, p, category="식비"), (2, 10000))
        self.assertEqual(transfer_io.export_csv(self.store, p, category=" 식비"), (2, 10000))
        self.assertEqual(transfer_io.export_csv(self.store, p, category="미분류"), (1, 1000))
        self.assertEqual(transfer_io.export_csv(self.store, p, category="없는분류"), (0, 0))
        self.assertEqual(transfer_io.export_json(self.store, p, "2026-11-01", "2026-11-30", "식비"), (0, 0))

    def test_empty_writes_header_only(self):
        p = self.path("e.csv")
        self.assertEqual(transfer_io.export_csv(self.store, p, "2027-01-01", "2027-01-31"), (0, 0))
        with open(p, encoding="utf-8-sig") as f:
            self.assertEqual(f.read().strip(), ",".join(transfer_io.CSV_FIELDS))

    def test_json_content(self):
        p = self.path("a.json")
        self.assertEqual(transfer_io.export_json(self.store, p), (4, 17000))
        with open(p, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("회의 후 저녁", text)  # ensure_ascii=False
        data = json.loads(text)
        self.assertEqual([e["id"] for e in data], [1, 2, 3, 5])
        self.assertEqual(data[1], self.store.get_expense(2))

    def test_does_not_change_store(self):
        before = copy.deepcopy(self.store.data)
        transfer_io.export_csv(self.store, self.path("a.csv"), category="식비")
        transfer_io.export_json(self.store, self.path("a.json"))
        self.assertEqual(self.store.data, before)

    def test_errors(self):
        p = self.path("a.csv")
        with self.assertRaises(ValueError):
            transfer_io.export_csv(self.store, p, "2026-11-30", "2026-11-01")
        with self.assertRaises(ValueError):
            transfer_io.export_csv(self.store, p, category=3)
        with self.assertRaises(OSError):
            transfer_io.export_json(self.store, self.path("없는폴더/a.json"))

    def test_command(self):
        from moim import cli
        out = []
        args = cli.build_parser().parse_args(
            ["io", "export-csv", self.path("m.csv"), "--month", "2026-11", "--category", "교통"])
        self.assertFalse(cli.run(args, self.cfg, self.store, out.append))
        self.assertEqual(out, [f"내보냈습니다: {self.path('m.csv')} (1건, 합계 6,000원)"])
        args = cli.build_parser().parse_args(["io", "export-json", self.path("m.json")])
        cli.run(args, self.cfg, self.store, out.append)
        self.assertIn("(4건, 합계 17,000원)", out[-1])


class VerifyExportTest(ExportData):
    """file_total · verify_export: 내보낸 파일 합계 검사."""

    def write(self, name, text, encoding="utf-8"):
        p = self.path(name)
        with open(p, "w", encoding=encoding, newline="") as f:
            f.write(text)
        return p

    def test_file_total_matches_export(self):
        for name, fn in (("a.csv", transfer_io.export_csv), ("a.json", transfer_io.export_json)):
            p = self.path(name)
            count, total = fn(self.store, p)
            self.assertEqual(transfer_io.file_total(p), (total, count))   # 스켈레톤: (합계, 건수)
            self.assertEqual(transfer_io.file_total(p), (17000, 4))
            fn(self.store, p, category="식비")
            self.assertEqual(transfer_io.file_total(p), (10000, 2))

    def test_file_total_empty(self):
        p = self.path("e.csv")
        transfer_io.export_csv(self.store, p, "2027-01-01", "2027-01-31")
        self.assertEqual(transfer_io.file_total(p), (0, 0))
        self.assertEqual(transfer_io.file_total(self.write("e.json", "[]")), (0, 0))
        self.assertEqual(transfer_io.file_total(self.write("z.csv", "")), (0, 0))

    def test_file_total_csv_forms(self):
        # BOM 없는 UTF-8, CP949, 쉼표 금액, 대문자 확장자, 열 순서가 달라도 amount 열로 읽음
        text = 'memo,amount\n저녁,"9,000"\n택시,1000\n'
        self.assertEqual(transfer_io.file_total(self.write("u.csv", text)), (10000, 2))
        self.assertEqual(transfer_io.file_total(self.write("c.csv", text, "cp949")), (10000, 2))
        self.assertEqual(transfer_io.file_total(self.write("J.JSON", '[{"amount": 5}]')), (5, 1))

    def test_file_total_bad_csv(self):
        cases = {
            "no_col.csv": "id,date\n1,2026-11-01\n",
            "short.csv": "id,amount\n1,100\n2\n",
            "long.csv": "id,amount\n1,100,9\n",
            "word.csv": "id,amount\n1,abc\n",
            "zero.csv": "id,amount\n1,0\n",
            "blank.csv": "id,amount\n1,\n",
        }
        for name, text in cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                transfer_io.file_total(self.write(name, text))
        with self.assertRaisesRegex(ValueError, "3번 줄"):
            transfer_io.file_total(self.write("line.csv", "id,amount\n1,100\n2,-5\n"))

    def test_file_total_bad_json(self):
        for text in ("{", '{"amount": 1}', "[1]", '[{"id": 1}]', '[{"amount": true}]', '[{"amount": "x"}]'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                transfer_io.file_total(self.write("b.json", text))

    def test_file_total_missing_file(self):
        with self.assertRaises(OSError):
            transfer_io.file_total(self.path("없음.csv"))
        with self.assertRaises(OSError):
            transfer_io.file_total(self.path("없음.json"))

    def test_verify_after_export(self):
        for name, fn in (("v.csv", transfer_io.export_csv), ("v.json", transfer_io.export_json)):
            p = self.path(name)
            fn(self.store, p)
            self.assertEqual(transfer_io.verify_export(self.store, p), (True, 17000, 17000))
            fn(self.store, p, "2026-11-01", "2026-11-30", "교통")
            self.assertEqual(transfer_io.verify_export(self.store, p, "2026-11-01", "2026-11-30", "교통"),
                             (True, 6000, 6000))

    def test_verify_detects_changes(self):
        p = self.path("v.csv")
        transfer_io.export_csv(self.store, p)
        self.store.get_expense(2)["deleted"] = True          # 내보낸 뒤 기록이 바뀜
        self.assertEqual(transfer_io.verify_export(self.store, p), (False, 17000, 11000))
        transfer_io.export_csv(self.store, p, category="식비")  # 다른 조건으로 내보낸 파일
        self.assertFalse(transfer_io.verify_export(self.store, p)[0])

    def test_verify_compares_total_only(self):
        # 스켈레톤: "내보낸 파일 합계가 원래 기록 합계와 같은가" — 건수는 보지 않는다
        p = self.write("x.csv", "id,amount\n1,10000\n2,7000\n")   # 합계 17,000원, 2건(기록은 4건)
        self.assertEqual(transfer_io.verify_export(self.store, p), (True, 17000, 17000))
        self.assertEqual(transfer_io.export_count(self.store), 4)
        self.assertEqual(transfer_io.export_count(self.store, "2026-11-01", "2026-11-30", "교통"), 1)

    def test_verify_record_total_is_period_total(self):
        # 기록 합계는 공통 조회 함수(period_total)와 같은 값 — 보고서·정산과 같은 기준
        p = self.path("v.csv")
        for start, end in ((None, None), ("2026-11-01", "2026-11-30"), ("2026-11-01", None)):
            transfer_io.export_csv(self.store, p, start, end)
            self.assertEqual(transfer_io.verify_export(self.store, p, start, end)[2],
                             period_total(self.store, start, end))

    def test_verify_does_not_change_store(self):
        p = self.path("v.json")
        transfer_io.export_json(self.store, p)
        before = copy.deepcopy(self.store.data)
        transfer_io.verify_export(self.store, p)
        self.assertEqual(self.store.data, before)

    def test_verify_command(self):
        from moim import cli
        p = self.path("cmd.csv")
        transfer_io.export_csv(self.store, p, "2026-11-01", "2026-11-30")
        out = []
        args = cli.build_parser().parse_args(["io", "verify", p, "--month", "2026-11"])
        self.assertFalse(cli.run(args, self.cfg, self.store, out.append))
        args = cli.build_parser().parse_args(["io", "verify", p])
        cli.run(args, self.cfg, self.store, out.append)
        args = cli.build_parser().parse_args(["io", "verify", self.write("y.csv", "amount\n4000\n3000\n")])
        cli.run(args, self.cfg, self.store, out.append)
        self.assertEqual(out, [
            "일치합니다: 파일 합계 7,000원 = 기록 합계 7,000원",
            "일치하지 않습니다: 파일 합계 7,000원, 기록 합계 17,000원 (차이 -10,000원)",
            "참고: 건수가 다릅니다(파일 2건, 기록 4건)",
            "일치하지 않습니다: 파일 합계 7,000원, 기록 합계 17,000원 (차이 -10,000원)",
            "참고: 건수가 다릅니다(파일 2건, 기록 4건)",
        ])
        out.clear()
        args = cli.build_parser().parse_args(["io", "verify", self.write("w.csv", "amount\n10000\n7000\n")])
        cli.run(args, self.cfg, self.store, out.append)
        self.assertEqual(out, ["일치합니다: 파일 합계 17,000원 = 기록 합계 17,000원",
                               "참고: 건수가 다릅니다(파일 2건, 기록 4건)"])


class ImportCsvTest(StoreCase):
    """import_csv: CSV 가져오기, 열 이름 연결, 오류 줄 번호. 명부는 규격 2장의 S."""

    HEAD = "date,payer,amount,members,weights,category,memo\n"

    def setUp(self):
        super().setUp()
        self.store.data["members"] = [
            {"name": "양정현", "joined": "2026-09-01", "left": None},
            {"name": "신동훈", "joined": "2026-09-01", "left": "2026-11-30"},
            {"name": "이은경", "joined": "2026-09-01", "left": None},
        ]

    def write(self, text, name="in.csv", encoding="utf-8"):
        p = self.path(name)
        with open(p, "w", encoding=encoding, newline="") as f:
            f.write(text)
        return p

    def imp(self, text, **kw):
        return transfer_io.import_csv(self.store, self.write(text), **kw)

    def test_import_fields_and_history(self):
        r = self.imp(self.HEAD + "2026-11-17,양정현,\"9,000\",양정현;이은경,양정현=2,식비,회의 후 저녁\n"
                                 "2026-11-18,이은경,1000,이은경,,,\n")
        self.assertEqual(r, {"encoding": "utf-8-sig", "added": [1, 2], "duplicates": [], "errors": []})
        e1, e2 = self.store.data["expenses"]
        self.assertEqual((e1["date"], e1["payer"], e1["amount"], e1["members"], e1["weights"], e1["category"],
                          e1["memo"]), ("2026-11-17", "양정현", 9000, ["양정현", "이은경"], {"양정현": 2}, "식비",
                                        "회의 후 저녁"))
        self.assertEqual((e2["weights"], e2["category"], e2["memo"]), (None, None, ""))  # 빈 분류칸 → None
        self.assertEqual([h["action"] for h in self.store.data["history"]], ["import", "import"])

    def test_roundtrip_with_export(self):
        self.imp(self.HEAD + "2026-11-17,양정현,9000,양정현;신동훈;이은경,양정현=2;이은경=1,식비,저녁\n"
                             "2026-11-20,신동훈,4000,양정현;신동훈,,,택시\n")
        before = copy.deepcopy(self.store.data["expenses"])
        p = self.path("out.csv")
        transfer_io.export_csv(self.store, p)
        self.store.data["expenses"] = []
        self.assertEqual(transfer_io.import_csv(self.store, p)["added"], [3, 4])  # 번호는 새로 매김
        for old, new in zip(before, self.store.data["expenses"]):
            old.pop("id"), new.pop("id")
            self.assertEqual(old, new)

    def test_empty_members_means_all_active(self):
        self.imp(self.HEAD + "2026-11-30,양정현,3000,,,,\n2026-12-01,양정현,2000,,,,\n")
        self.assertEqual(self.store.data["expenses"][0]["members"], ["양정현", "신동훈", "이은경"])
        self.assertEqual(self.store.data["expenses"][1]["members"], ["양정현", "이은경"])   # 탈퇴 다음 날

    def test_mapping_and_cp949(self):
        text = "번호,날짜,낸 사람,금액,메모\n7,2026-11-17,양정현,9000,저녁\n"
        p = self.write(text, "k.csv", "cp949")
        r = transfer_io.import_csv(self.store, p, {"날짜": "date", "낸 사람": "payer", "금액": "amount",
                                                   "메모": "memo"})
        self.assertEqual((r["encoding"], r["added"]), ("cp949", [1]))
        self.assertEqual(self.store.data["expenses"][0]["memo"], "저녁")
        with self.assertRaisesRegex(ValueError, "date, payer, amount"):   # 연결 없이 읽으면 필요한 열이 없음
            transfer_io.import_csv(self.store, p)

    def test_error_rows_reported_and_rest_imported(self):
        r = self.imp(self.HEAD + "2026-02-30,양정현,1000,,,,\n"
                                 "2026-11-17,양정현,0,,,,\n"
                                 "2026-11-17,없는사람,1000,,,,\n"
                                 "2026-11-17,양정현\n"
                                 "2026-11-17,양정현,1000,양정현,양정현=x,,\n"
                                 "2026-12-01,양정현,1000,신동훈,,,\n"
                                 "2026-11-17,이은경,1000,,,,정상\n")
        self.assertEqual(r["added"], [1])
        self.assertEqual([n for n, _ in r["errors"]], [2, 3, 4, 5, 6, 7])
        self.assertIn("날짜", r["errors"][0][1])
        self.assertIn("1원 이상", r["errors"][1][1])
        self.assertIn("없는사람", r["errors"][2][1])
        self.assertIn("열 수", r["errors"][3][1])
        self.assertIn("비율", r["errors"][4][1])
        self.assertIn("신동훈", r["errors"][5][1])      # 탈퇴 다음 날은 참여자 불가

    def test_duplicates_existing_and_in_file(self):
        # 중복 기준은 ledger.duplicates(규격 18): 같은 날·같은 낸 사람·같은 금액
        self.imp(self.HEAD + "2026-11-17,양정현,9000,,,,\n")
        r = self.imp(self.HEAD + "2026-11-17,양정현,\"9,000\",,,,메모가 달라도 중복\n"   # 이미 있는 지출과 같음
                                 "2026-11-18,이은경,500,,,,\n"
                                 "2026-11-18,이은경,500,,,,\n"                       # 파일 앞줄과 같음
                                 "2026-11-18,양정현,500,,,,\n"                       # 낸 사람이 다르면 중복 아님
                                 "2026-11-18,이은경,501,,,,\n")                      # 금액이 다르면 중복 아님
        self.assertEqual(r, {"encoding": "utf-8-sig", "added": [2, 3, 4], "duplicates": [2, 4], "errors": []})
        self.assertEqual(len(self.store.data["expenses"]), 4)

    def test_same_file_twice_adds_nothing(self):
        text = self.HEAD + "2026-11-17,양정현,9000,,,,\n2026-11-18,이은경,500,,,,\n"
        self.assertEqual(self.imp(text)["added"], [1, 2])
        before = copy.deepcopy(self.store.data)
        r = self.imp(text)
        self.assertEqual((r["added"], r["duplicates"]), ([], [2, 3]))
        self.assertEqual(self.store.data, before)          # 지출·번호·이력 모두 그대로

    def test_deleted_expense_is_not_duplicate(self):
        self.imp(self.HEAD + "2026-11-17,양정현,9000,,,,\n")
        self.store.data["expenses"][0]["deleted"] = True
        r = self.imp(self.HEAD + "2026-11-17,양정현,9000,,,,\n")
        self.assertEqual((r["added"], r["duplicates"]), ([2], []))

    def test_error_reported_before_duplicate(self):
        self.imp(self.HEAD + "2026-11-17,양정현,9000,,,,\n")
        r = self.imp(self.HEAD + "2026-11-17,양정현,9000,없는사람,,,\n")   # 중복이지만 참여자가 잘못됨
        self.assertEqual((r["duplicates"], [n for n, _ in r["errors"]]), ([], [2]))

    def test_bad_input(self):
        self.assertEqual(self.imp(""), {"encoding": "utf-8-sig", "added": [], "duplicates": [], "errors": []})
        before = copy.deepcopy(self.store.data)
        with self.assertRaises(ValueError):
            self.imp("date,amount\n2026-11-17,1000\n")       # payer 열 없음
        with self.assertRaises(NotImplementedError):        # 미리 보기는 아직 구현 전
            self.imp(self.HEAD + "2026-11-17,양정현,1000,,,,\n", preview=True)
        with self.assertRaises(OSError):
            transfer_io.import_csv(self.store, self.path("없음.csv"))
        self.assertEqual(self.store.data, before)

    def test_import_command(self):
        from moim import cli
        p = self.write("날짜,낸 사람,금액\n2026-11-17,양정현,9000\n2026-11-31,양정현,1\n")
        out = []
        args = cli.build_parser().parse_args(["io", "import", p, "--map", "날짜=date;낸 사람=payer;금액=amount"])
        self.assertTrue(cli.run(args, self.cfg, self.store, out.append))      # 자료를 바꿨으니 저장
        self.assertEqual(out[0], "가져왔습니다(utf-8-sig): 1건 - 지출 번호 1")
        self.assertTrue(out[1].startswith("오류 3번 줄: 날짜가 잘못되었습니다"))
        out.clear()
        args = cli.build_parser().parse_args(["io", "import", self.write("날짜\n", "e.csv"), "--map", "날짜=date"])
        self.assertFalse(cli.run(args, self.cfg, self.store, out.append))     # 넣은 것이 없으면 저장 안 함
        with self.assertRaises(ValueError):
            cli.run(cli.build_parser().parse_args(["io", "import", p, "--map", "날짜"]), self.cfg, self.store,
                    out.append)

    def test_import_command_reports_duplicates(self):
        from moim import cli
        p = self.write("날짜,낸 사람,금액\n2026-11-17,양정현,9000\n2026-11-17,양정현,9000\n2026-11-31,양정현,1\n")
        out = []
        args = cli.build_parser().parse_args(["io", "import", p, "--map", "날짜=date;낸 사람=payer;금액=amount"])
        self.assertTrue(cli.run(args, self.cfg, self.store, out.append))
        self.assertEqual(out[:2], ["가져왔습니다(utf-8-sig): 1건 - 지출 번호 1", "중복이라 건너뜀: 3번 줄"])
        self.assertTrue(out[2].startswith("오류 4번 줄: "))
        out.clear()
        self.assertFalse(cli.run(args, self.cfg, self.store, out.append))   # 다시 가져오면 모두 중복 → 저장 안 함
        self.assertEqual(out[:2], ["가져왔습니다(utf-8-sig): 0건", "중복이라 건너뜀: 2, 3번 줄"])
        for line in out:
            line.encode("cp949")                                            # 기본 Windows 콘솔에서도 출력됨

    def test_io_outputs_fit_cp949_console(self):
        # 기본 Windows 콘솔(cp949)에서 출력하다 UnicodeEncodeError 로 멈추면 가져온 지출이 저장되지 않는다
        from moim import cli
        p = self.write("날짜,낸 사람,금액\n2026-11-17,양정현,9000\n2026-11-18,양정현,1000\n2026-11-31,양정현,1\n")
        e = self.path("e.csv")
        out = []
        for argv in (["io", "import", p, "--map", "날짜=date;낸 사람=payer;금액=amount"],
                     ["io", "export-csv", e, "--month", "2026-11"],
                     ["io", "export-json", self.path("e.json")],
                     ["io", "verify", e, "--month", "2026-11"],
                     ["io", "verify", self.write("amount\n1\n", "x.csv")]):
            cli.run(cli.build_parser().parse_args(argv), self.cfg, self.store, out.append)
        self.assertEqual(len(out), 7)   # import 2줄(결과·오류), export 2줄, verify 3줄(일치, 불일치·건수 참고)
        for line in out:
            with self.subTest(line=line):
                line.encode("cp949")


if __name__ == "__main__":
    unittest.main()
