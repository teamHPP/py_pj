"""조회 함수. 여러 기능이 같은 계산을 쓰므로 여기 한 곳에만 둔다. 함수마다 설명 끝에 담당 기능이 있다."""

from . import dates, money  # noqa: F401
from .rules import UNCATEGORIZED  # noqa: F401


def expenses_in(store, start, end, include_deleted=False):
    """기간 안의 지출 목록(시작일·끝일 포함). 담당: 기능 3"""
    raise NotImplementedError("기능 3 담당이 구현한다")


def period_total(store, start, end):
    """기간 합계. 담당: 기능 6"""
    raise NotImplementedError("기능 6 담당이 구현한다")


def category_of(e):
    """지출의 분류 이름. 분류가 없으면 규약의 "미분류". 담당: 기능 2"""
    raise NotImplementedError("기능 2 담당이 구현한다")


def category_totals(store, start, end):
    """분류별 건수와 금액. {분류: {"count": n, "amount": 원}} 담당: 기능 2"""
    raise NotImplementedError("기능 2 담당이 구현한다")


def person_paid(store, start, end):
    """사람마다 낸 돈 합계. 담당: 기능 3"""
    raise NotImplementedError("기능 3 담당이 구현한다")


def is_member_active(store, name, on):
    """그날 모임 회원인가. 가입일 이상, 탈퇴일 이하(탈퇴일 당일까지는 회원). 담당: 기능 5"""
    raise NotImplementedError("기능 5 담당이 구현한다")


def active_members(store, on):
    """그날의 회원 이름 목록(명부 순서). 담당: 기능 5"""
    raise NotImplementedError("기능 5 담당이 구현한다")


def expense_shares(e):
    """지출 하나의 사람별 부담액. 담당: 기능 4"""
    raise NotImplementedError("기능 4 담당이 구현한다")


def member_shares(store, start, end):
    """기간 동안 사람마다 부담할 돈 합계. 담당: 기능 4"""
    raise NotImplementedError("기능 4 담당이 구현한다")


def is_locked(store, on):
    """정산이 확정된 기간에 속하는 날짜인가. 담당: 기능 4

    store.data["locks"]: [{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}]. 기간은 시작일·끝일 모두 포함.
    locks 가 없거나 비어 있으면 False. 조회만 하고 자료는 바꾸지 않는다.
    """
    day = dates.parse(on)  # None·빈 값·없는 날짜는 locks 가 없어도 ValueError
    locks = store.data.get("locks", [])
    if not isinstance(locks, list):
        raise ValueError("확정 기간(locks)은 목록이어야 합니다")
    locked = False
    for lock in locks:
        if not isinstance(lock, dict) or "start" not in lock or "end" not in lock:
            raise ValueError(f"확정 기간 형식이 잘못되었습니다(start·end 필요): {lock}")
        start, end = dates.parse(lock["start"]), dates.parse(lock["end"])
        if start > end:
            raise ValueError(f"확정 기간의 시작일이 끝일보다 늦습니다: {lock['start']} ~ {lock['end']}")
        if dates.in_period(day, start, end):
            locked = True
    return locked
