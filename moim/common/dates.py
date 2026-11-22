"""날짜·기간 규칙: YYYY-MM-DD, 기간은 시작일과 끝일을 모두 포함."""

import calendar
import datetime as dt

from .rules import DATE_FORMAT


def parse(value):
    """'2026-11-12' 형식의 문자열을 date 로 바꾼다. 없는 날짜면 ValueError."""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.datetime.strptime(str(value).strip(), DATE_FORMAT).date()
    except ValueError:
        raise ValueError(f"날짜가 잘못되었습니다(YYYY-MM-DD, 실제 있는 날짜): {value}") from None


def fmt(value):
    return parse(value).strftime(DATE_FORMAT)


def parse_month(text):
    """'2026-11' -> (2026, 11)"""
    try:
        y, m = str(text).strip().split("-")
        y, m = int(y), int(m)
        if not 1 <= m <= 12:
            raise ValueError
        return y, m
    except ValueError:
        raise ValueError(f"달 형식이 잘못되었습니다(YYYY-MM): {text}") from None


def days_in_month(year, month):
    return calendar.monthrange(year, month)[1]


def month_range(year, month):
    """그달의 첫날과 말일. 기간 규칙상 둘 다 포함한다."""
    return dt.date(year, month, 1), dt.date(year, month, days_in_month(year, month))


def in_period(value, start, end):
    """value 가 start~end 기간 안에 있는가. 시작일·끝일 모두 포함."""
    d = parse(value)
    return parse(start) <= d <= parse(end)


def month_key(value):
    raise NotImplementedError("기능 6 담당이 구현한다")


def prev_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def next_month(year, month):
    return (year + 1, 1) if month == 12 else (year, month + 1)


def months_between(start_ym, end_ym):
    """(y,m) 부터 (y,m) 까지 달 목록. 둘 다 포함.

    규격: docs/공통모듈_함수규격.md 17
    - 입력은 (연도, 월) tuple. 연도 1~9999, 월 1~12, bool 은 받지 않는다
    - "YYYY-MM" 문자열은 부르는 쪽이 parse_month 로 바꿔서 넘긴다
    - 시작 달이 끝 달보다 뒤이거나 입력이 잘못되면 ValueError
    예: months_between((2026, 11), (2027, 1)) -> [(2026, 11), (2026, 12), (2027, 1)]
    """
    start = _check_ym(start_ym, "시작 달")
    end = _check_ym(end_ym, "끝 달")
    if start > end:
        raise ValueError(f"시작 달이 끝 달보다 뒤입니다: {start} > {end}")
    out = []
    ym = start
    while ym <= end:
        out.append(ym)
        ym = next_month(*ym)
    return out


def _check_ym(value, label):
    """(연도, 월) tuple 인지 검사하고 그대로 돌려준다. 잘못되면 ValueError. (months_between 전용)"""
    if not isinstance(value, tuple) or len(value) != 2:
        raise ValueError(f"{label}은 (연도, 월) tuple 이어야 합니다: {value!r}")
    y, m = value
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (y, m)):
        raise ValueError(f"{label}의 연도·월은 정수여야 합니다: {value!r}")
    if not (1 <= y <= 9999 and 1 <= m <= 12):
        raise ValueError(f"{label}의 범위가 잘못되었습니다(연도 1~9999, 월 1~12): {value!r}")
    return (y, m)


def today():
    return dt.date.today()
