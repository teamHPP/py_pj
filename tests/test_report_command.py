"""기능 3(월별·기간 보고서) 담당의 테스트. 보고서 글(report.month_report·period_report·monthly_report)과 명령 `report` 를 확인한다.

다른 기능 3 테스트 파일과 나눠, 같은 기능 3의 다른 PR과 같은 줄을 고치지 않게 했다.
"""

import copy
import unittest

from helpers import StoreCase

from moim import cli
from moim.features import report

KIM, LEE = "김민수", "이서연"

MONTH_2026_11 = (
    "2026-11 지출 보고서\n"
    "합계 18,000원 (3건), 지난달 1,000원, 증감 +17,000원 (+1700.0%)\n"
    "\n"
    "분류별\n"
    "분류      금액\n"
    "------  ------\n"
    "교통     9,000\n"
    "식비     6,000\n"
    "미분류   3,000\n"
    "------  ------\n"
    "합계    18,000\n"
    "\n"
    "사람별(낸 돈)\n"
    "이름      금액\n"
    "------  ------\n"
    "김민수  12,000\n"
    "이서연   6,000\n"
    "------  ------\n"
    "합계    18,000")


def expense(eid, date, payer, amount, category="식비", deleted=False):
    """테스트용 지출 한 건. 기능 1의 add_expense 를 거치지 않고 store.data["expenses"] 에 바로 넣는다."""
    return {"id": eid, "date": date, "payer": payer, "amount": amount, "members": [KIM, LEE],
            "category": category, "memo": "", "deleted": deleted, "weights": None, "recurring_id": None}


class ReportCase(StoreCase):
    def setUp(self):
        super().setUp()
        self.store.data["expenses"].extend([
            expense(1, "2026-11-12", LEE, 6000), expense(2, "2026-11-13", KIM, 9000, category="교통"),
            expense(3, "2026-11-20", KIM, 3000, category=None), expense(4, "2026-10-05", LEE, 1000),
            expense(5, "2026-11-21", LEE, 50000, deleted=True)])

    def run_cmd(self, *argv):
        out = []
        changed = cli.run(cli.build_parser().parse_args(["report", *argv]), self.cfg, self.store, out.append)
        return changed, "\n".join(out)


class ReportTextTest(ReportCase):
    def test_month_report(self):
        # 스켈레톤 안내서 8장 월 보고서 모양: 분류별·사람별 표는 금액 큰 순서, 삭제된 지출(5번)은 빠짐
        self.assertEqual(report.month_report(self.store, "2026-11"), MONTH_2026_11)

    def test_period_report_title_and_range(self):
        got = report.period_report(self.store, "2026-11-12", "2026-11-13")
        self.assertEqual(got.split("\n")[:2], ["2026-11-12 ~ 2026-11-13 지출 보고서", "합계 15,000원 (2건)"])
        self.assertNotIn("미분류", got)   # 11-20 지출은 기간 밖

    def test_period_report_same_body_as_month(self):
        # 기간 보고서에는 전월 대비가 없고, 표는 월 보고서와 같다
        got = report.period_report(self.store, "2026-11-01", "2026-11-30").split("\n")
        self.assertEqual(got[1], "합계 18,000원 (3건)")
        self.assertEqual(got[2:], MONTH_2026_11.split("\n")[2:])

    def test_same_amount_keeps_first_order(self):
        self.store.data["expenses"] = [expense(1, "2026-11-12", LEE, 5000), expense(2, "2026-11-13", KIM, 5000)]
        lines = report.month_report(self.store, "2026-11").split("\n")
        self.assertLess(lines.index("이서연   5,000"), lines.index("김민수   5,000"))

    def test_empty(self):
        self.assertEqual(report.month_report(self.store, "2026-12"),
                         "2026-12 지출 보고서\n"
                         "합계 0원 (0건), 지난달 18,000원, 증감 -18,000원 (-100.0%)\n"
                         "이 기간에 지출이 없습니다")

    def test_monthly_report(self):
        self.assertEqual(report.monthly_report(self.store, "2026-09", "2026-11"),
                         "2026-09 ~ 2026-11 월별 지출\n"
                         "달         금액\n"
                         "-------  ------\n"
                         "2026-09       0\n"
                         "2026-10   1,000\n"
                         "2026-11  18,000\n"
                         "-------  ------\n"
                         "합계     19,000")

    def test_store_not_changed(self):
        before = copy.deepcopy(self.store.data)
        report.month_report(self.store, "2026-11")
        report.period_report(self.store, "2026-11-01", "2026-11-30")
        report.monthly_report(self.store, "2026-10", "2026-11")
        self.assertEqual(self.store.data, before)

    def test_bad_input(self):
        cases = [
            (report.month_report, ("2026-13",)),
            (report.month_report, ("2026/11",)),
            (report.period_report, (None, "2026-11-30")),            # 시작일 없음
            (report.period_report, ("2026-11-30", "2026-11-01")),    # 시작일 > 끝일
            (report.monthly_report, ("2026-12", "2026-11")),         # 시작 달 > 끝 달
        ]
        for fn, args in cases:
            with self.subTest(fn=fn.__name__, args=args), self.assertRaises(ValueError):
                fn(self.store, *args)


class ReportCommandTest(ReportCase):
    def test_month(self):
        self.assertEqual(self.run_cmd("month", "2026-11"), (False, MONTH_2026_11))

    def test_period_with_start_end(self):
        changed, text = self.run_cmd("period", "--start", "2026-11-12", "--end", "2026-11-13")
        self.assertFalse(changed)
        self.assertEqual(text, report.period_report(self.store, "2026-11-12", "2026-11-13"))

    def test_period_with_month(self):
        changed, text = self.run_cmd("period", "--month", "2026-10")
        self.assertEqual(text.split("\n")[:2], ["2026-10-01 ~ 2026-10-31 지출 보고서", "합계 1,000원 (1건)"])

    def test_period_needs_range(self):
        with self.assertRaises(ValueError):
            self.run_cmd("period", "--start", "2026-11-01")

    def test_months(self):
        self.assertEqual(self.run_cmd("months", "2026-09", "2026-11"),
                         (False, report.monthly_report(self.store, "2026-09", "2026-11")))

    def test_no_subcommand(self):
        self.assertEqual(self.run_cmd(), (False, "아직 만들지 않은 명령입니다: report"))


if __name__ == "__main__":
    unittest.main()
