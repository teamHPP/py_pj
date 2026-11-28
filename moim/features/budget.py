"""기능 5. 예산·회비.

이 기능을 구현하려면 아래 공통 함수를 이 기능 담당자가 채운다(공통 모듈 병합 요청으로).
  - common/queries.py is_member_active — 그날 회원인가(공용: 기능 1의 지출 검사)
  - common/queries.py active_members — 그날 회원 목록
  - common/dates.py months_between — 두 달 사이의 달 목록(공용: 기능 3)
  - 은행 거래내역 가져오기는 기능 6이 채우는 common/csvio.py 의 read_csv_rows 를 쓴다

이 기능에 필요한 자료 항목은 common/store.py 의 EMPTY 에 이 기능 담당자가 추가한다.
  - 회비 입금(payments 목록)

아래 함수의 이름과 인자는 바꾸지 않는다(인수 테스트와 채점이 이 이름으로 실행된다).
필요하면 함수를 더 만들어도 된다. 다른 기능 파일은 불러 쓰지 않는다.
"""

import copy

from ..common import dates, ledger, money
from ..common.csvio import read_csv_rows
from ..common.queries import active_members, category_totals, period_total


def month_status(store, cfg, month, today=None):
    """이번 달 예산 상태. today 를 주면 그날까지의 지출만 센다.

    - month: "YYYY-MM". 기간은 그달 1일부터 말일까지(규약 3, 양끝 포함)
    - 월 예산은 설정 파일의 cfg["budget"]["monthly"] (0 이상의 원 단위 정수)
    - 지출은 period_total(19) 로만 센다(삭제 제외·기간 경계가 보고서·정산과 같게)
    - today 가 그달 1일보다 앞이면 지출 0. period_total 은 시작일 > 끝일이면 ValueError 라 부르기 전에 막는다
    - 돌려주는 값: {"month", "budget", "spent", "remaining", "over"}
      remaining = budget - spent (넘으면 음수), over = spent > budget (정확히 예산만큼은 초과 아님)
    """
    start, end = dates.month_range(*dates.parse_month(month))
    limit = monthly_budget(cfg)
    if today is not None:
        end = min(end, dates.parse(today))
    spent = period_total(store, start, end) if start <= end else 0
    return {
        "month": dates.month_key(start),
        "budget": limit,
        "spent": spent,
        "remaining": limit - spent,
        "over": spent > limit,
    }


def monthly_budget(cfg):
    """설정 파일의 월 예산 cfg["budget"]["monthly"]. 없거나 0 이상의 정수가 아니면 ValueError."""
    section = cfg.get("budget") if isinstance(cfg, dict) else None
    value = section.get("monthly") if isinstance(section, dict) else None
    if value is None:
        raise ValueError('설정 파일에 월 예산이 없습니다("budget": {"monthly": 원})')
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"월 예산은 0 이상의 원 단위 정수여야 합니다: {value!r}")
    return value


def category_status(store, cfg, month):
    """분류별 예산 상태. {분류: {"budget", "spent", "remaining", "over", "warn"}}"""
    raise NotImplementedError("이 함수를 구현한다")


def forecast(store, month, today):
    """지금 속도로 쓰면 월말 합계가 얼마가 되는지. (오늘까지 지출 / 지난 일수) x 그달 일수."""
    raise NotImplementedError("이 함수를 구현한다")


def record_payment(store, date, member, amount, memo=""):
    """회비 입금을 기록한다.

    - date: 실제 있는 날짜(YYYY-MM-DD 로 저장), amount: 원 단위로 사사오입한 1원 이상
    - member: 명부에 있는 이름(공통모듈_함수규격 "기능 5가 더하는 자료 항목" payments 표)
    - store.data["payments"] 에 {"id", "date", "member", "amount", "memo", "source": "manual"} 를 더한다.
      id 는 기존 id 의 최댓값 + 1. 디스크 저장은 명령 쪽(통합 실행)이 한다
    - 돌려주는 값: 저장한 입금 기록의 복사본. 잘못된 입력은 이유를 담은 ValueError(그때 자료는 바뀌지 않음)
    """
    day = dates.fmt(date)
    try:
        won = money.to_won(amount)
    except (ValueError, ArithmeticError):
        raise ValueError(f"금액 형식이 잘못되었습니다: {amount!r}") from None
    if won < 1:
        raise ValueError(f"회비 금액은 1원 이상이어야 합니다: {amount!r}")
    if not isinstance(member, str) or store.member(member) is None:
        raise ValueError(f"명부에 없는 사람입니다: {member!r}")
    if not isinstance(memo, str):
        raise ValueError(f"메모는 문자열이어야 합니다: {memo!r}")
    payments = store.data.get("payments")
    if not isinstance(payments, list):
        raise ValueError("회비 입금(payments)은 목록이어야 합니다")
    new_id = max((p["id"] for p in payments), default=0) + 1
    p = {"id": new_id, "date": day, "member": member, "amount": won, "memo": memo, "source": "manual"}
    payments.append(p)
    return copy.deepcopy(p)


def treasury_balance(store, until=None):
    """모임 통장 잔고 = 회비 입금 합계 - 지출 합계(until 날짜까지).

    - until: 그날까지(당일 포함, 규약 3). None 이면 처음부터 끝까지 전부
    - 회비 입금은 store.data["payments"], 지출 합계는 period_total(19) 로만 센다(삭제된 지출 제외)
    - 돌려주는 값: 원 단위 int. 지출이 더 많으면 음수. 자료가 없으면 0
    - 잘못된 until 이나 payments 자료는 이유를 담은 ValueError. Store 는 바꾸지 않는다
    """
    end = None if until is None else dates.parse(until)
    paid_in = sum(p["amount"] for p in _payments_until(store, end))
    return paid_in - period_total(store, None, end)


def _payments_until(store, end):
    """end 날짜까지(포함)의 회비 입금 기록. end 가 None 이면 전부. 자료 모양이 잘못되면 ValueError."""
    items = store.data.get("payments", [])
    if not isinstance(items, list):
        raise ValueError("회비 입금(payments)은 목록이어야 합니다")
    picked = []
    for p in items:
        if not isinstance(p, dict) or not isinstance(p.get("date"), str):
            raise ValueError(f"회비 입금 기록 형식이 잘못되었습니다: {p!r}")
        amount = p.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 1:
            raise ValueError(f"회비 입금 금액이 잘못되었습니다(1원 이상의 정수): {amount!r}")
        day = dates.parse(p["date"])
        if end is None or day <= end:
            picked.append(p)
    return picked


def unpaid(store, cfg, month):
    """그달 회비 미납자. 그달 1일 또는 말일에 회원인 사람이 대상. [(이름, 낸 회비, 모자란 금액)]

    - 대상: 그달 1일이나 말일에 회원인 사람(회원 판단은 active_members → is_member_active), 명부 순서
    - 낸 회비: 그달 1일~말일(양끝 포함)에 그 사람 이름으로 들어온 회비 입금 합계
    - 1인당 월 회비는 설정 파일의 cfg["dues"]["monthly"](0 이상의 원 단위 정수). 낸 회비가 그보다 적은 사람만 넣는다
    - 모두 냈으면 []. 잘못된 달·설정·자료는 이유를 담은 ValueError. Store 는 바꾸지 않는다
    """
    first, last = dates.month_range(*dates.parse_month(month))
    dues = monthly_dues(cfg)
    on_first, on_last = active_members(store, first), active_members(store, last)
    targets = on_first + [n for n in on_last if n not in on_first]
    order = [m["name"] for m in store.data["members"]]
    targets.sort(key=order.index)
    paid = {}
    for p in _payments_until(store, last):
        if dates.parse(p["date"]) >= first:
            paid[p["member"]] = paid.get(p["member"], 0) + p["amount"]
    return [(n, paid.get(n, 0), dues - paid.get(n, 0)) for n in targets if paid.get(n, 0) < dues]


def monthly_dues(cfg):
    """설정 파일의 1인당 월 회비 cfg["dues"]["monthly"]. 없거나 0 이상의 정수가 아니면 ValueError."""
    section = cfg.get("dues") if isinstance(cfg, dict) else None
    value = section.get("monthly") if isinstance(section, dict) else None
    if value is None:
        raise ValueError('설정 파일에 1인당 월 회비가 없습니다("dues": {"monthly": 원})')
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"1인당 월 회비는 0 이상의 원 단위 정수여야 합니다: {value!r}")
    return value


def dues_deduction(store, cfg, month):
    """회비를 덜 낸 사람에게 정산에서 차감할 금액. {이름: 모자란 회비}"""
    raise NotImplementedError("이 함수를 구현한다")


def budget_table(store, cfg, month):
    """예산 대비 실제 표 자료. [(분류, 예산, 실제, 차이)] 마지막 줄은 전체."""
    raise NotImplementedError("이 함수를 구현한다")


def suggest_budget(store, month):
    """다음 달 예산 제안: 그달을 포함한 최근 3개월 지출 평균(천 원 단위 올림)."""
    raise NotImplementedError("이 함수를 구현한다")

BANK_COLUMNS = ["거래일자", "거래시각", "적요", "출금액", "입금액", "잔액"]


def import_bank(store, path, treasurer):
    """가상 은행(Tarnwick 제휴 은행) 거래내역을 가져온다(docs/은행거래내역형식.md).
    출금 → 총무가 낸 지출(참여자: 그날의 회원 전원), 입금 → 적요의 이름으로 회비 입금.
    이미 들어간 거래(같은 날·같은 금액·같은 적요의 출금, 같은 날·같은 사람·같은 금액의 은행 입금)와
    파일 안에서 거래일자·거래시각·적요·금액·잔액이 모두 같은 줄은 중복으로 보고 건너뛴다.
    돌려주는 값: {"expenses": [번호], "payments": 건수, "duplicates": [줄 번호], "errors": [(줄 번호, 오류)]}"""
    raise NotImplementedError("이 함수를 구현한다")
