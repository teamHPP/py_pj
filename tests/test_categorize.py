"""기능 2(분류 규칙) 담당의 테스트. 공통 함수 queries.category_of 의 규격(docs/공통모듈_함수규격.md 03절)을 확인한다."""

import copy
import unittest

import helpers  # noqa: F401  (저장소 맨 위 폴더를 import 경로에 넣는다)

from moim.common.queries import category_of
from moim.common.rules import UNCATEGORIZED

P = ["양정현", "신동훈", "이은경"]


def expense(**kw):
    """규격 2장 예시 자료 S 의 e. 필요한 항목만 바꿔서 쓴다."""
    e = {"id": 1, "date": "2026-11-17", "payer": "양정현", "amount": 9000,
         "members": list(P), "category": "식비", "memo": "회의 후 저녁",
         "deleted": False, "weights": None, "recurring_id": None}
    e.update(kw)
    return e


class CategoryOfTest(unittest.TestCase):
    def test_spec_examples(self):
        self.assertEqual(category_of(expense()), "식비")
        self.assertEqual(category_of({"category": " 식비 "}), "식비")
        self.assertEqual(category_of({"category": None}), "미분류")
        self.assertEqual(category_of({"category": "  "}), "미분류")
        self.assertEqual(category_of({"category": "미분류"}), "미분류")
        with self.assertRaises(ValueError):
            category_of({"category": 3})

    def test_uncategorized_name_is_rule_value(self):
        # 규약 5장: 분류가 없는 지출은 rules.UNCATEGORIZED 로 센다
        self.assertEqual(category_of({"category": None}), UNCATEGORIZED)

    def test_missing_key_and_empty(self):
        self.assertEqual(category_of({}), "미분류")
        self.assertEqual(category_of({"category": ""}), "미분류")
        self.assertEqual(category_of({"category": "\t\n "}), "미분류")
        e = expense()
        del e["category"]
        self.assertEqual(category_of(e), "미분류")

    def test_strip_keeps_inner_spaces(self):
        self.assertEqual(category_of({"category": "  장소 대여 "}), "장소 대여")

    def test_ignores_category_fixed(self):
        # 고정 여부와 상관없이 지금 적힌 분류를 돌려준다
        self.assertEqual(category_of(expense(category="교통", category_fixed=True)), "교통")
        self.assertEqual(category_of(expense(category=None, category_fixed=True)), "미분류")

    def test_does_not_change_expense(self):
        e = expense(category=" 식비 ")
        before = copy.deepcopy(e)
        category_of(e)
        self.assertEqual(e, before)

    def test_not_dict(self):
        for bad in (None, [], "식비", 3):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    category_of(bad)
        with self.assertRaisesRegex(ValueError, "지출은 dict여야 합니다"):
            category_of(None)

    def test_bad_category_type(self):
        for bad in (3, 1.5, True, ["식비"], {"이름": "식비"}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    category_of({"category": bad})


if __name__ == "__main__":
    unittest.main()
