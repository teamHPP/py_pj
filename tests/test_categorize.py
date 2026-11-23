"""기능 2(분류 규칙) 담당의 테스트. 공통 함수 queries.category_of·category_totals 의 규격(docs/공통모듈_함수규격.md 03·04절)을 확인한다."""

import copy
import json
import os
import unittest

from helpers import StoreCase

from moim.common.queries import category_of, category_totals, expenses_in
from moim.features import categorize
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


class CategoryTotalsTest(StoreCase):
    def setUp(self):
        super().setUp()
        self.e = expense()   # 규격 2장 예시 자료 S 의 e
        self.store.data["expenses"].append(self.e)

    def put(self, *items):
        self.store.data["expenses"].extend(items)

    def test_spec_examples(self):
        self.assertEqual(category_totals(self.store, "2026-11-01", "2026-11-30"),
                         {"식비": {"count": 1, "amount": 9000}})
        self.assertEqual(category_totals(self.store, "2026-12-01", "2026-12-31"), {})
        with self.assertRaises(ValueError):
            category_totals(self.store, "2026-11-30", "2026-11-01")

    def test_spec_example_uncategorized(self):
        self.put(expense(id=2, date="2026-11-18", payer="이은경", amount=3000, category=None, memo=""))
        self.assertEqual(category_totals(self.store, None, None),
                         {"식비": {"count": 1, "amount": 9000}, "미분류": {"count": 1, "amount": 3000}})

    def test_spec_example_deleted(self):
        self.e["deleted"] = True
        self.assertEqual(category_totals(self.store, "2026-11-01", "2026-11-30"), {})

    def test_empty(self):
        self.store.data["expenses"].clear()
        self.assertEqual(category_totals(self.store, None, None), {})

    def test_both_ends_included(self):
        # 규약 3장: 기간은 시작일과 끝일을 모두 포함한다
        self.put(expense(id=2, date="2026-10-31", amount=1000),
                 expense(id=3, date="2026-11-01", amount=2000),
                 expense(id=4, date="2026-11-30", amount=4000),
                 expense(id=5, date="2026-12-01", amount=8000))
        self.assertEqual(category_totals(self.store, "2026-11-01", "2026-11-30"),
                         {"식비": {"count": 3, "amount": 15000}})

    def test_same_category_and_uncategorized_grouped(self):
        # None·공백·키 없음·" 식비 " 가 category_of 로 같은 분류에 묶인다
        no_key = expense(id=6, amount=600)
        del no_key["category"]
        self.put(expense(id=2, amount=200, category=" 식비 "),
                 expense(id=3, amount=300, category=None),
                 expense(id=4, amount=400, category="  "),
                 expense(id=5, amount=500, category="미분류"),
                 no_key)
        self.assertEqual(category_totals(self.store, None, None),
                         {"식비": {"count": 2, "amount": 9200}, "미분류": {"count": 4, "amount": 1800}})

    def test_key_order_follows_expenses_in(self):
        # key 순서는 expenses_in 결과((date, id) 오름차순)에서 처음 나온 순서
        self.put(expense(id=2, date="2026-11-10", category="교통"),
                 expense(id=3, date="2026-11-17", category="물품"),
                 expense(id=4, date="2026-11-20", category="교통"))
        self.assertEqual(list(category_totals(self.store, None, None)), ["교통", "식비", "물품"])

    def test_sums_match_expenses_in(self):
        self.put(expense(id=2, date="2026-11-03", amount=12345, category="교통"),
                 expense(id=3, date="2026-11-21", amount=777, category=None),
                 expense(id=4, date="2026-11-25", amount=5000, category="교통", deleted=True))
        picked = expenses_in(self.store, "2026-11-01", "2026-11-30")
        totals = category_totals(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(sum(v["count"] for v in totals.values()), len(picked))
        self.assertEqual(sum(v["amount"] for v in totals.values()), sum(x["amount"] for x in picked))
        for v in totals.values():
            self.assertIsInstance(v["count"], int)
            self.assertIsInstance(v["amount"], int)

    def test_new_dict_and_store_unchanged(self):
        before = copy.deepcopy(self.store.data)
        first = category_totals(self.store, None, None)
        first["식비"]["amount"] = 0
        self.assertEqual(category_totals(self.store, None, None), {"식비": {"count": 1, "amount": 9000}})
        self.assertEqual(self.store.data, before)

    def test_bad_category_raises(self):
        self.put(expense(id=2, category=3))
        with self.assertRaises(ValueError):
            category_totals(self.store, None, None)


class RuleFileTest(StoreCase):
    """기본 필수: 분류 규칙을 JSON 파일로 저장하고 읽기."""

    def test_save_load_round_trip(self):
        rules = []
        categorize.add_rule(rules, "식비", ["저녁", "회식"], priority=2)
        categorize.add_rule(rules, "장소 대여", payer="양정현", min_amount="10,000", max_amount=50000)
        path = self.path("sub/rules.json")
        categorize.save_rules(path, rules)
        self.assertEqual(categorize.load_rules(path), rules)
        with open(path, encoding="utf-8") as f:
            self.assertIn("식비", f.read())   # 한글을 \uXXXX 로 바꾸지 않고 저장
        self.assertEqual([n for n in os.listdir(self.path("sub")) if n.endswith(".tmp")], [])

    def test_missing_file_is_empty(self):
        self.assertEqual(categorize.load_rules(self.path("none.json")), [])

    def test_broken_file(self):
        for text in ("{깨짐", json.dumps({"category": "식비"}), json.dumps([{"keywords": []}])):
            with self.subTest(text=text):
                with open(self.path("bad.json"), "w", encoding="utf-8") as f:
                    f.write(text)
                with self.assertRaises(ValueError):
                    categorize.load_rules(self.path("bad.json"))


class AddRemoveRuleTest(unittest.TestCase):
    """기본 필수: 규칙 추가·삭제."""

    def test_add_rule_shape_and_order(self):
        rules = []
        first = categorize.add_rule(rules, " 식비 ", [" 저녁 ", "", "저녁", "회식"])
        categorize.add_rule(rules, "교통", ["택시"], priority=1)
        self.assertEqual(first, {"category": "식비", "keywords": ["저녁", "회식"], "priority": 0,
                                 "payer": None, "min_amount": None, "max_amount": None})
        self.assertEqual([r["category"] for r in rules], ["식비", "교통"])

    def test_amounts_use_to_won(self):
        rule = categorize.add_rule([], "물품", min_amount="1,000.5", max_amount="2,000원")
        self.assertEqual((rule["min_amount"], rule["max_amount"]), (1001, 2000))

    def test_add_rule_errors(self):
        bad = [dict(category=""), dict(category=None, keywords=["a"]), dict(keywords="저녁"),
               dict(keywords=[3]), dict(keywords=["a"], priority="1"), dict(keywords=["a"], priority=True),
               dict(payer=" "), dict(min_amount=-1), dict(min_amount=5000, max_amount=1000),
               dict(keywords=[" "])]
        for kw in bad:
            with self.subTest(kw=kw):
                rules = []
                kw = {"category": "식비", **kw}
                with self.assertRaises(ValueError):
                    categorize.add_rule(rules, **kw)
                self.assertEqual(rules, [])

    def test_remove_rule(self):
        rules = []
        categorize.add_rule(rules, "식비", ["저녁"])
        categorize.add_rule(rules, "교통", ["택시"])
        self.assertEqual(categorize.remove_rule(rules, 1)["category"], "교통")
        for index in (1, -1, True, "0"):
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    categorize.remove_rule(rules, index)
        self.assertEqual([r["category"] for r in rules], ["식비"])


class RuleCommandsTest(StoreCase):
    """기본 필수: 규칙 추가·삭제·목록 명령 (moim cat add/remove/list)."""

    def run_cmd(self, argv):
        from moim import cli
        out = []
        changed = cli.run(cli.build_parser().parse_args(argv), self.cfg, self.store, out.append)
        return changed, out

    def test_add_list_remove(self):
        self.assertEqual(self.run_cmd(["cat", "list"]), (False, ["분류 규칙이 없습니다"]))
        changed, out = self.run_cmd(["cat", "add", "식비", "--keywords", "저녁;회식", "--priority", "2"])
        self.assertFalse(changed)   # 규칙은 자료 파일이 아니라 규칙 파일에 저장한다
        self.assertIn("1번 식비", out[-1])
        self.run_cmd(["cat", "add", "장소 대여", "--payer", "김민수", "--min", "10000"])
        _, out = self.run_cmd(["cat", "list"])
        self.assertEqual(len(out), 2)
        self.assertIn("2번 장소 대여", out[1])
        self.run_cmd(["cat", "remove", "1"])
        self.assertEqual([r["category"] for r in categorize.load_rules(self.cfg["rules"])], ["장소 대여"])

    def test_errors(self):
        with self.assertRaises(ValueError):
            self.run_cmd(["cat", "add", "식비"])          # 조건 없음
        with self.assertRaisesRegex(ValueError, "없는 규칙 번호입니다: 1 "):
            self.run_cmd(["cat", "remove", "1"])          # 없는 번호는 화면 번호(1부터) 그대로 알린다
        with self.assertRaisesRegex(ValueError, "없는 규칙 번호입니다: 0 "):
            self.run_cmd(["cat", "remove", "0"])
        self.assertFalse(os.path.exists(self.cfg["rules"]))


if __name__ == "__main__":
    unittest.main()
