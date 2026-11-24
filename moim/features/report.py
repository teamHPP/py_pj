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
    """기간 합계·분류별 합계·사람별(낸 돈) 합계.

    돌려주는 값: {"total": 원, "count": 건수, "by_category": {분류: 원}, "by_person": {낸 사람: 원}}
    - 기간은 시작일·끝일 포함(규약 3), 삭제된 지출은 뺀다. start·end 가 None 이면 그쪽은 제한이 없다
    - total 은 period_total(19), 분류별은 category_totals(04), 사람별은 person_paid(06) 로 센다
      (세 값 모두 expenses_in 을 거쳐서 보고서·정산·내보내기와 같은 기준)
    - key 순서는 그 기간 지출에서 처음 나온 순서. 지출이 없으면 total·count 는 0, 나머지는 {}
    - 시작일 > 끝일은 부르기 전에 직접 확인해 ValueError(규격 1장 ⚠). 잘못된 날짜·지출 자료는 각 함수의 ValueError
    - Store 는 바꾸지 않는다
    """
    if start is not None and end is not None and dates.parse(start) > dates.parse(end):
        raise ValueError(f"시작일이 끝일보다 늦습니다: {dates.fmt(start)} > {dates.fmt(end)}")
    by_category = category_totals(store, start, end)
    return {
        "total": period_total(store, start, end),
        "count": sum(c["count"] for c in by_category.values()),
        "by_category": {name: c["amount"] for name, c in by_category.items()},
        "by_person": person_paid(store, start, end),
    }


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
    """한 달 보고서 글. 제목·합계(건수)·분류별 표·사람별(낸 돈) 표. 명령 `report month` 가 찍는다.

    - 그달 1일~말일을 period_summary 로 센다(합계를 따로 세지 않음)
    - 'YYYY-MM' 이 아닌 달은 ValueError
    """
    year, mon = dates.parse_month(month)
    start, end = dates.month_range(year, mon)
    return _report_text(f"{year:04d}-{mon:02d} 지출 보고서", period_summary(store, start, end))


def period_report(store, start, end):
    """기간 보고서 글. month_report 와 같은 모양이고 제목만 'YYYY-MM-DD ~ YYYY-MM-DD'. 명령 `report period` 가 찍는다.

    - start·end 는 둘 다 있어야 한다(None 이면 ValueError). 시작일 > 끝일 등은 period_summary 의 ValueError
    """
    if start is None or end is None:
        raise ValueError("보고서 기간의 시작일과 끝일을 모두 지정하십시오")
    summary = period_summary(store, start, end)
    return _report_text(f"{dates.fmt(start)} ~ {dates.fmt(end)} 지출 보고서", summary)


def monthly_report(store, start_month, end_month):
    """여러 달의 월별 합계 표 글. 지출이 없는 달도 0원으로 한 줄. 명령 `report months` 가 찍는다.

    - 값은 monthly_totals 로만 센다. 잘못된 달·시작 달 > 끝 달은 monthly_totals 의 ValueError
    """
    totals = monthly_totals(store, start_month, end_month)
    months = list(totals)
    rows = [[ym, amount] for ym, amount in totals.items()]
    body = table(["달", "금액"], rows, total=["합계", sum(totals.values())], numeric={1})
    return f"{months[0]} ~ {months[-1]} 월별 지출\n{body}"


def _by_amount(totals):
    """{이름: 원} 을 금액이 큰 순서의 [이름, 원] 목록으로. 금액이 같으면 원래(처음 나온) 순서."""
    return [[name, amount] for name, amount in sorted(totals.items(), key=lambda item: -item[1])]


def _report_text(title, summary):
    """보고서 본문. 지출이 없으면 표 대신 안내 한 줄."""
    lines = [title, f"합계 {money.fmt(summary['total'])}원 ({summary['count']}건)"]
    if not summary["count"]:
        lines.append("이 기간에 지출이 없습니다")
        return "\n".join(lines)
    for heading, label, totals in (("분류별", "분류", summary["by_category"]),
                                   ("사람별(낸 돈)", "이름", summary["by_person"])):
        lines += ["", heading,
                  table([label, "금액"], _by_amount(totals), total=["합계", summary["total"]], numeric={1})]
    return "\n".join(lines)


def save_report(text, path):
    """보고서를 텍스트 파일(.txt)로 저장한다."""
    raise NotImplementedError("이 함수를 구현한다")


def search(store, start=None, end=None, person=None, min_amount=None, max_amount=None, word=None):
    """지출 검색. 기간, 사람(낸 사람이거나 참여자), 금액 범위, 메모 낱말로 찾는다. 삭제된 지출은 빼고 날짜순."""
    raise NotImplementedError("이 함수를 구현한다")
