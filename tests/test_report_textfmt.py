"""기능 3(월별·기간 보고서) 담당의 테스트. 공통 함수 textfmt.table·bar_chart 의 규격(docs/공통모듈_함수규격.md 07·08절)을 확인한다.

queries 테스트(tests/test_report.py)와 파일을 나눠, 같은 기능 3의 다른 PR과 같은 줄을 고치지 않게 했다.
"""

import copy
import unittest

from moim.common.textfmt import bar_chart, table


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


class BarChartTest(unittest.TestCase):
    # 규격 08절 예시
    def test_spec_examples(self):
        self.assertEqual(bar_chart({"식비": 2, "교통": 1}, bar_width=4), "식비 | #### 2\n교통 | ## 1")
        self.assertEqual(bar_chart({"a": 100, "b": 10}, bar_width=4), "a | #### 100\nb |  10")   # b는 내림이라 0칸

    def test_spec_empty(self):
        self.assertEqual(bar_chart({}), "")
        self.assertEqual(bar_chart({"식비": 0}), "식비 |  0")
        self.assertEqual(bar_chart({"a": 0, "b": 0}), "a |  0\nb |  0")   # 모두 0이면 모두 0칸

    def test_default_width_like_month_report(self):
        # 스켈레톤 안내서의 월 보고서 막대그래프와 같은 값: 최댓값은 30칸, 588,400은 30 × 588400 // 924500 = 19칸
        self.assertEqual(bar_chart({"식비": 924500, "미분류": 588400}),
                         "식비   | " + "#" * 30 + " 924,500\n"
                         "미분류 | " + "#" * 19 + " 588,400")

    def test_name_width_uses_screen_width(self):
        # 한글은 2칸이라 "식비"(4칸)에 맞춰 "etc"(3칸) 뒤에 공백 1칸
        self.assertEqual(bar_chart({"식비": 1, "etc": 2}, bar_width=2), "식비 | # 1\netc  | ## 2")

    def test_keeps_dict_order(self):
        self.assertEqual(bar_chart({"b": 1, "a": 2}, bar_width=2), "b | # 1\na | ## 2")

    def test_other_char(self):
        self.assertEqual(bar_chart({"식비": 2, "교통": 1}, bar_width=4, char="="), "식비 | ==== 2\n교통 | == 1")

    def test_no_trailing_newline_and_input_not_changed(self):
        data = {"식비": 9000, "교통": 3000}
        before = dict(data)
        got = bar_chart(data)
        self.assertFalse(got.endswith("\n"))
        self.assertEqual(data, before)

    def test_negative_value_message(self):
        with self.assertRaises(ValueError) as cm:
            bar_chart({"식비": -1})
        self.assertEqual(str(cm.exception), "막대 값은 0 이상의 정수여야 합니다")

    def test_bad_input(self):
        cases = [
            ([("식비", 1)], {}),        # dict 가 아님
            ({1: 1}, {}),               # str 이 아닌 key
            ({"a": True}, {}),          # bool 값
            ({"a": 1.5}, {}),           # 정수가 아닌 값
            ({"a": "3"}, {}),
            ({"a": None}, {}),
            ({"a": 1}, {"bar_width": 0}),       # 0 이하 폭
            ({"a": 1}, {"bar_width": -1}),
            ({"a": 1}, {"bar_width": True}),    # bool 폭
            ({"a": 1}, {"bar_width": 2.0}),     # 정수가 아닌 폭
            ({"a": 1}, {"char": ""}),           # 빈 문자열
            ({"a": 1}, {"char": "##"}),         # 두 글자 이상
            ({"a": 1}, {"char": "가"}),         # 폭 2칸
            ({"a": 1}, {"char": "\n"}),         # 줄바꿈
            ({"a": 1}, {"char": "\t"}),         # 제어문자
            ({"a": 1}, {"char": 1}),
        ]
        for data, kw in cases:
            with self.subTest(data=data, kw=kw), self.assertRaises(ValueError):
                bar_chart(data, **kw)


if __name__ == "__main__":
    unittest.main()
