"""기능 5 확장 필수: 은행 거래내역 가져오기(import_bank). 담당: 김정빈

파일 형식은 docs/은행거래내역형식.md. 명부는 helpers 의 김민수·이서연·박지훈(2026-09-01 가입).
"""

import json

from helpers import NAMES, StoreCase

from moim.features import budget

HEAD = "거래일자,거래시각,적요,출금액,입금액,잔액\n"


class ImportBank(StoreCase):
    def bank(self, body, encoding="cp949", head=HEAD, name="bank.csv"):
        path = self.path(name)
        with open(path, "w", encoding=encoding, newline="") as f:
            f.write(head + body)
        return path

    def run_import(self, path, treasurer="김민수"):
        return budget.import_bank(self.store, path, treasurer)

    def test_doc_example(self):
        # 문서의 예(CP949): 2번 줄 입금, 3번 줄 쉼표 금액 출금
        path = self.bank('2026.11.01,09:10,이서연,,20000,20000\n'
                         '2026.11.03,19:42,회의 후 저녁,"48,000",,-28000\n')
        result = self.run_import(path)
        self.assertEqual(result, {"expenses": [1], "payments": 1, "duplicates": [], "errors": []})
        e = self.store.data["expenses"][0]
        self.assertEqual((e["date"], e["payer"], e["amount"], e["members"], e["memo"]),
                         ("2026-11-03", "김민수", 48000, NAMES, "회의 후 저녁"))
        self.assertEqual(self.store.data["payments"],
                         [{"id": 1, "date": "2026-11-01", "member": "이서연", "amount": 20000,
                           "memo": "", "source": "bank"}])
        self.assertEqual(self.store.data["history"][-1]["action"], "bank_import")

    def test_zero_is_empty_and_utf8(self):
        # tools/gen_data.py 는 쓰지 않는 금액 칸에 0 을 적는다. UTF-8 파일도 읽는다
        path = self.bank("2026.11.02,10:00,박지훈,0,20000,20000\n"
                         "2026.11.05,12:00,점심 김밥,9000,0,11000\n", encoding="utf-8")
        result = self.run_import(path)
        self.assertEqual((result["expenses"], result["payments"]), ([1], 1))

    def test_columns_by_name(self):
        path = self.bank("20000,,이서연,09:10,2026.11.01,20000\n",
                         head="잔액,출금액,적요,거래시각,거래일자,입금액\n")
        self.assertEqual(self.run_import(path)["payments"], 1)

    def test_participants_are_members_of_that_day(self):
        self.store.data["members"][2]["left"] = "2026-11-10"   # 박지훈 11/10 탈퇴(당일까지 회원)
        path = self.bank("2026.11.10,19:00,음료,6000,,1\n2026.11.11,19:00,음료,4000,,1\n")
        self.run_import(path)
        self.assertEqual([e["members"] for e in self.store.data["expenses"]], [NAMES, ["김민수", "이서연"]])

    def test_same_file_twice_is_not_added_twice(self):
        # 같은 날·같은 금액·같은 적요라도 시각이 다른 두 거래는 둘 다 들어가고, 다시 가져오면 둘 다 건너뜀
        path = self.bank("2026.11.04,10:00,음료,4000,,1\n2026.11.04,15:00,음료,4000,,2\n"
                         "2026.11.06,09:00,이서연,,20000,3\n")
        self.assertEqual(self.run_import(path), {"expenses": [1, 2], "payments": 1, "duplicates": [], "errors": []})
        before = json.dumps(self.store.data, sort_keys=True)
        self.assertEqual(self.run_import(path), {"expenses": [], "payments": 0, "duplicates": [2, 3, 4], "errors": []})
        self.assertEqual(json.dumps(self.store.data, sort_keys=True), before)

    def test_exact_same_line_in_file(self):
        path = self.bank("2026.11.04,10:00,음료,4000,,1\n2026.11.04,10:00,음료,4000,,1\n")
        self.assertEqual(self.run_import(path)["duplicates"], [3])
        self.assertEqual(len(self.store.data["expenses"]), 1)

    def test_existing_records(self):
        # 이미 있는 지출(같은 날·금액·적요)은 건너뛰고, 직접 입력한 회비는 은행 입금과 겹쳐도 따로 본다
        budget.record_payment(self.store, "2026-11-06", "이서연", 20000)
        self.store.data["expenses"].append(
            {"id": 1, "date": "2026-11-04", "payer": "이서연", "amount": 4000, "members": NAMES,
             "memo": "음료", "category": None, "deleted": False, "weights": None, "recurring_id": None})
        path = self.bank("2026.11.04,10:00,음료,4000,,1\n2026.11.06,09:00,이서연,,20000,3\n")
        self.assertEqual(self.run_import(path), {"expenses": [], "payments": 1, "duplicates": [2], "errors": []})

    def test_bad_lines_are_reported_and_rest_imported(self):
        path = self.bank("2026.11.01,09:00,이서연,,20000,1\n"
                         "2026.11.02,09:00,홍길동,,20000,1\n"        # 3: 명부에 없는 이름
                         "2026.11.02,09:00,음료,4000,4000,1\n"       # 4: 출금·입금 함께
                         "2026.11.02,09:00,음료,0,,1\n"              # 5: 둘 다 없음
                         "2026-11-02,09:00,음료,4000,,1\n"           # 6: 날짜 형식
                         "2026.02.30,09:00,음료,4000,,1\n"           # 7: 없는 날짜
                         "2026.11.02,09:00,음료,사천원,,1\n"         # 8: 금액 형식
                         "2026.11.02,09:00,음료,-4000,,1\n"          # 9: 음수
                         "2026.11.02,09:00, ,4000,,1\n"              # 10: 적요 없음
                         "2026.11.02,09:00,음료,4000\n"              # 11: 열 수
                         "2026.08.02,09:00,음료,4000,,1\n"           # 12: 그날 회원이 없음
                         "2026.11.03,09:00,음료,4000,,1\n")
        result = self.run_import(path)
        self.assertEqual([line for line, _ in result["errors"]], list(range(3, 13)))
        self.assertTrue(all(isinstance(msg, str) and msg for _, msg in result["errors"]))
        self.assertEqual((result["expenses"], result["payments"]), ([1], 1))

    def test_whole_file_errors(self):
        with self.assertRaises(ValueError):
            self.run_import(self.bank("2026.11.01,이서연,,20000\n", head="거래일자,적요,출금액,입금액\n"))
        path = self.bank("")
        for treasurer in ("", None, "홍길동"):
            with self.subTest(treasurer=treasurer), self.assertRaises(ValueError):
                self.run_import(path, treasurer)
        with self.assertRaises(OSError):
            self.run_import(self.path("none.csv"))

    def test_empty_file(self):
        self.assertEqual(self.run_import(self.bank("")),
                         {"expenses": [], "payments": 0, "duplicates": [], "errors": []})
