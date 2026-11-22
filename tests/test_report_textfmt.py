"""기능 3(월별·기간 보고서) 담당의 테스트. 공통 함수 textfmt.table 의 규격(docs/공통모듈_함수규격.md 07절)을 확인한다.

queries 테스트(tests/test_report.py)와 파일을 나눠, 같은 기능 3의 다른 PR과 같은 줄을 고치지 않게 했다.
"""

import copy
import unittest

from moim.common.textfmt import table


class TableTest(unittest.TestCase):
    # 규격 07절 예시
    def test_spec_examples(self):
        self.assertEqual(table(["A"], [["B"]]), "A\n-\nB")
        self.assertEqual(table(["금액"], [[9000]], total=[9000], numeric={0}),
                         " 금액\n-----\n9,000\n-----\n9,000")
        self.assertEqual(table(["이름", "금액"], [["양정현", 9000]], total=["합계", 9000], numeric={1}),
                         "이름     금액\n"
                         "------  -----\n"
                         "양정현  9,000\n"
                         "------  -----\n"
                         "합계    9,000")

    def test_spec_empty(self):
        self.assertEqual(table(["금액"], [], numeric={0}), "금액")
        self.assertEqual(table(["A"], [], total=["T"]), "A\n-\nT")

    def test_int_comma_in_any_column(self):
        # int 셀은 열과 관계없이 쉼표, numeric 이 아닌 열은 왼쪽 정렬
        self.assertEqual(table(["번호", "금액"], [[1000, 5], ["7", 12345]], numeric={1}),
                         "번호     금액\n"
                         "-----  ------\n"
                         "1,000       5\n"
                         "7      12,345")

    def test_width_includes_total(self):
        # 열 폭은 headers · rows · total 중 가장 넓은 값
        self.assertEqual(table(["금액"], [[1]], total=[1000000], numeric={0}),
                         "     금액\n---------\n        1\n---------\n1,000,000")

    def test_negative_int(self):
        self.assertEqual(table(["증감"], [[-1500]], numeric={0}), "  증감\n------\n-1,500")

    def test_empty_header_text_allowed(self):
        self.assertEqual(table(["", "x"], [["a", "b"]]), "   x\n-  -\na  b")

    def test_no_trailing_space_or_newline(self):
        got = table(["이름", "메모"], [["가", "길다란메모"], ["나나", ""]], total=["합계", ""])
        self.assertFalse(got.endswith("\n"))
        for line in got.split("\n"):
            self.assertEqual(line, line.rstrip())

    def test_inputs_not_changed(self):
        headers, rows, total, numeric = ["이름", "금액"], [["양정현", 9000]], ["합계", 9000], {1}
        before = copy.deepcopy((headers, rows, total, numeric))
        table(headers, rows, total=total, numeric=numeric)
        self.assertEqual((headers, rows, total, numeric), before)

    def test_column_count_message(self):
        with self.assertRaises(ValueError) as cm:
            table(["금액"], [[9000, 1]])
        self.assertEqual(str(cm.exception), "행의 열 수가 제목과 다릅니다")

    def test_bad_input(self):
        cases = [
            ([], [], None, None),               # 빈 headers
            ("금액", [], None, None),            # list 가 아닌 headers
            ([1], [], None, None),              # str 이 아닌 제목
            (["A"], [["a", "b"]], None, None),  # 행의 열 수 불일치
            (["A"], [], ["T", "U"], None),      # total 의 열 수 불일치
            (["A"], [["a"]], None, {1}),        # 범위 밖 열 번호
            (["A"], [["a"]], None, {-1}),
            (["A"], [["a"]], None, {True}),     # bool 열 번호
            (["A"], [["a"]], None, {0.0}),      # 정수가 아닌 열 번호
            (["A"], [[True]], None, None),      # bool 셀
            (["A"], [[1.5]], None, None),       # float 셀
            (["A"], [[None]], None, None),      # None 셀
            (["A"], [], [None], None),          # total 의 None 셀
        ]
        for headers, rows, total, numeric in cases:
            with self.subTest(headers=headers, rows=rows, total=total, numeric=numeric):
                with self.assertRaises(ValueError):
                    table(headers, rows, total=total, numeric=numeric)


if __name__ == "__main__":
    unittest.main()
