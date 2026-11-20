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
    """그날 모임 회원인가. 가입일 이상, 탈퇴일 이하(탈퇴일 당일까지는 회원). 담당: 기능 5

    규격: docs/공통모듈_함수규격.md 15
    - 명부가 비어 있거나 명부에 없는 이름이면 False
    - left 가 None 이면 끝나는 날이 없다
    - 빈 이름·str 이 아닌 이름, 잘못된 날짜, 그 사람의 잘못된 가입·탈퇴일이나 joined > left 는 ValueError
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"이름은 비어 있지 않은 문자열이어야 합니다: {name!r}")
    if on is None:
        raise ValueError("날짜가 비어 있습니다")
    day = dates.parse(on)  # 형식 오류는 명부를 보기 전에 먼저 알린다
    m = store.member(name)
    if m is None:
        return False
    joined, left = _member_period(m)
    return joined <= day and (left is None or day <= left)


def _member_period(m):
    """명부 한 사람의 (가입일, 탈퇴일 또는 None). 잘못된 날짜나 가입일 > 탈퇴일이면 ValueError."""
    name = m.get("name")
    try:
        joined = dates.parse(m.get("joined"))
        left = None if m.get("left") is None else dates.parse(m["left"])
    except ValueError as exc:
        raise ValueError(f"{name}의 가입·탈퇴일이 잘못되었습니다: {exc}") from None
    if left is not None and joined > left:
        raise ValueError(f"{name}의 가입일이 탈퇴일보다 늦습니다: {joined} > {left}")
    return joined, left


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
    """정산이 확정된 기간에 속하는 날짜인가. 담당: 기능 4"""
    raise NotImplementedError("기능 4 담당이 구현한다")
