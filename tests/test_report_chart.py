"""기능 3(월별·기간 보고서) 담당의 테스트. 보고서의 분류별·월별 막대그래프를 확인한다.

다른 기능 3 테스트 파일과 나눠, 같은 기능 3의 다른 PR과 같은 줄을 고치지 않게 했다.
"""

import unittest

from helpers import StoreCase

from moim.common.textfmt import bar_chart
from moim.features import report

KIM = "김민수"


def expense(eid, date, amount, category="식비", deleted=False):
    """테스트용 지출 한 건. 기능 1의 add_expense 를 거치지 않고 store.data["expenses"] 에 바로 넣는다."""
    return {"id": eid, "date": date, "payer": KIM, "amount": amount, "members": [KIM],
            "category": category, "memo": "", "deleted": deleted, "weights": None, "recurring_id": None}


def chart_part(text, heading):
    """보고서 글에서 heading 줄 다음부터 끝까지(그래프 줄들)."""
    lines = text.split("\n")
    return "\n".join(lines[lines.index(heading) + 1:])


class CategoryChartTest(StoreCase):
    def test_skeleton_guide_example(self):
        # 스켈레톤 안내서 8장 월 보고서: 식비 924,500 은 30칸, 미분류 588,400 은 19칸
        self.store.data["expenses"].extend([expense(1, "2026-11-02", 924500), expense(2, "2026-11-03", 588400, None)])
        text = report.month_report(self.store, "2026-11")
        self.assertEqual(chart_part(text, "분류별 막대그래프"),
                         "식비   | " + "#" * 30 + " 924,500\n"
                         "미분류 | " + "#" * 19 + " 588,400")
        self.assertTrue(text.endswith("588,400"))   # 그래프가 보고서 맨 끝, 마지막 개행 없음

    def test_order_is_amount_desc_like_table(self):
        # 분류별 표와 같은 순서(금액 큰 순서, 같으면 처음 나온 순서)
        self.store.data["expenses"].extend([expense(1, "2026-11-02", 1000, "교통"), expense(2, "2026-11-03", 5000),
                                            expense(3, "2026-11-04", 1000, "물품")])
        got = chart_part(report.month_report(self.store, "2026-11"), "분류별 막대그래프")
        self.assertEqual([line.split(" |")[0].strip() for line in got.split("\n")], ["식비", "교통", "물품"])

    def test_same_as_bar_chart_of_category_amounts(self):
        # 금액은 period_summary 의 by_category 그대로(보고서에서 따로 세지 않음), 삭제된 지출은 빠짐
        self.store.data["expenses"].extend([expense(1, "2026-11-02", 7000), expense(2, "2026-11-03", 2000, "교통"),
                                            expense(3, "2026-11-04", 9000, "교통", deleted=True)])
        got = chart_part(report.period_report(self.store, "2026-11-01", "2026-11-30"), "분류별 막대그래프")
        self.assertEqual(got, bar_chart({"식비": 7000, "교통": 2000}))

    def test_no_chart_when_empty(self):
        text = report.month_report(self.store, "2026-11")
        self.assertNotIn("막대그래프", text)
        self.assertTrue(text.endswith("이 기간에 지출이 없습니다"))


class MonthlyChartTest(StoreCase):
    def test_month_order_and_zero_months(self):
        self.store.data["expenses"].extend([expense(1, "2026-12-24", 3000), expense(2, "2026-10-05", 6000)])
        got = chart_part(report.monthly_report(self.store, "2026-10", "2027-01"), "월별 막대그래프")
        self.assertEqual(got, "2026-10 | " + "#" * 30 + " 6,000\n"
                              "2026-11 |  0\n"
                              "2026-12 | " + "#" * 15 + " 3,000\n"
                              "2027-01 |  0")

    def test_all_zero(self):
        got = chart_part(report.monthly_report(self.store, "2026-11", "2026-12"), "월별 막대그래프")
        self.assertEqual(got, "2026-11 |  0\n2026-12 |  0")


if __name__ == "__main__":
    unittest.main()
