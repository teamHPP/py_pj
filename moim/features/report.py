"""기능 3. 월별·기간 보고서.

이 기능을 구현하려면 아래 공통 함수를 이 기능 담당자가 채운다(공통 모듈 병합 요청으로).
  - common/queries.py expenses_in — 기간 안의 지출 목록(공용: 전원)
  - common/queries.py person_paid — 사람별 낸 돈(공용: 기능 4)
  - common/textfmt.py table, bar_chart — 글자 표와 막대그래프(공용: 기능 1·4·5의 명령)

아래 함수의 이름과 인자는 바꾸지 않는다(인수 테스트와 채점이 이 이름으로 실행된다).
필요하면 함수를 더 만들어도 된다. 다른 기능 파일은 불러 쓰지 않는다.
"""

import os
from ..common import dates, money
from ..common.textfmt import bar_chart, pad, table, width  # noqa: F401  (보고서 기능의 표 출력은 공통 함수로 제공)
from ..common.queries import category_totals, expenses_in, period_total, person_paid

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def monthly_totals(store, start_month, end_month):
    """{'YYYY-MM': 합계}

    - start_month 부터 end_month 까지(둘 다 포함) 모든 달을 달 순서대로 넣는다. 지출이 없는 달은 0
    - 지출은 expenses_in 으로 고른다(삭제 제외, 그달 1일·말일 포함). 합계는 원 단위 int
    - 'YYYY-MM' 이 아닌 달은 ValueError. Store 는 바꾸지 않는다
    - 시작 달 > 끝 달은 months_between 을 부르기 전에 직접 확인해 ValueError(규격 1장 ⚠, 17 주의)
    """
    start_ym, end_ym = dates.parse_month(start_month), dates.parse_month(end_month)
    if start_ym > end_ym:
        raise ValueError(f"시작 달이 끝 달보다 뒤입니다: {start_month} > {end_month}")
    months = dates.months_between(start_ym, end_ym)
    totals = {f"{y:04d}-{m:02d}": 0 for y, m in months}
    first = dates.month_range(*months[0])[0]
    last = dates.month_range(*months[-1])[1]
    for e in expenses_in(store, first, last):
        totals[e["date"][:7]] += e["amount"]
    return totals


def period_summary(store, start, end):
    raise NotImplementedError("이 함수를 구현한다")


def month_over_month(store, month):
    """전월 대비. 돌려주는 값: (이번 달, 지난달, 증감, 증감률 % 또는 None)"""
    raise NotImplementedError("이 함수를 구현한다")


def weekday_totals(store, start, end):
    raise NotImplementedError("이 함수를 구현한다")


def week_totals(store, start, end):
    """주(월요일 시작)별 합계. {'YYYY-MM-DD(그 주 월요일)': 합계}"""
    raise NotImplementedError("이 함수를 구현한다")


def top_expenses(store, start, end, n=5):
    raise NotImplementedError("이 함수를 구현한다")


def biggest_day(store, start, end):
    raise NotImplementedError("이 함수를 구현한다")


def month_report(store, month):
    raise NotImplementedError("이 함수를 구현한다")


def save_report(text, path):
    """보고서를 텍스트 파일(.txt)로 저장한다."""
    raise NotImplementedError("이 함수를 구현한다")


def search(store, start=None, end=None, person=None, min_amount=None, max_amount=None, word=None):
    """지출 검색. 기간, 사람(낸 사람이거나 참여자), 금액 범위, 메모 낱말로 찾는다. 삭제된 지출은 빼고 날짜순."""
    raise NotImplementedError("이 함수를 구현한다")
