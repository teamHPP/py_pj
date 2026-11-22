"""조회 함수. 여러 기능이 같은 계산을 쓰므로 여기 한 곳에만 둔다. 함수마다 설명 끝에 담당 기능이 있다."""

import copy

from . import dates, money  # noqa: F401
from .rules import UNCATEGORIZED  # noqa: F401


def _expense_day(e):
    """지출 한 건의 자료형을 검사하고 날짜(date)를 돌려준다. 잘못되면 ValueError. (expenses_in 전용)"""
    if not isinstance(e, dict):
        raise ValueError(f"지출 자료 형식이 잘못되었습니다: {e!r}")
    eid = e.get("id")
    if isinstance(eid, bool) or not isinstance(eid, int):
        raise ValueError(f"지출 id가 잘못되었습니다: {eid!r}")
    date = e.get("date")
    if not isinstance(date, str):
        raise ValueError(f"{eid}번 지출의 날짜가 잘못되었습니다: {date!r}")
    day = dates.parse(date)
    if dates.fmt(day) != date:
        raise ValueError(f"{eid}번 지출의 날짜가 YYYY-MM-DD 형식이 아닙니다: {date!r}")
    amount = e.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 1:
        raise ValueError(f"{eid}번 지출의 금액이 잘못되었습니다(1원 이상의 정수): {amount!r}")
    if not isinstance(e.get("deleted", False), bool):
        raise ValueError(f"{eid}번 지출의 삭제 표시가 잘못되었습니다: {e.get('deleted')!r}")
    return day


def expenses_in(store, start, end, include_deleted=False):
    """기간 안의 지출 목록(시작일·끝일 포함). 담당: 기능 3

    규격: docs/공통모듈_함수규격.md 05
    - start·end 가 None 이면 그쪽은 제한이 없다. 기간 판정은 dates.in_period 를 쓴다
    - 삭제된 지출(deleted=True)은 include_deleted=True 일 때만 넣는다. deleted 키가 없으면 False
    - (date, id) 오름차순의 깊은 복사본. 원본을 고치려면 store.get_expense(id)
    - 날짜 오류, 시작일 > 끝일, bool 이 아닌 include_deleted, 저장소의 잘못된 지출(기간 밖 포함)은 ValueError
    """
    if not isinstance(include_deleted, bool):
        raise ValueError(f"include_deleted 는 True 나 False 여야 합니다: {include_deleted!r}")
    first = None if start is None else dates.parse(start)
    last = None if end is None else dates.parse(end)
    if first is not None and last is not None and first > last:
        raise ValueError(f"시작일이 끝일보다 늦습니다: {first} > {last}")
    items = store.data.get("expenses")
    if not isinstance(items, list):
        raise ValueError("지출 목록 형식이 잘못되었습니다")

    picked = []
    for e in items:
        day = _expense_day(e)
        if e.get("deleted", False) and not include_deleted:
            continue
        if not dates.in_period(day, day if first is None else first, day if last is None else last):
            continue
        picked.append((day, e["id"], e))
    picked.sort(key=lambda item: (item[0], item[1]))
    return [copy.deepcopy(e) for _, _, e in picked]


def period_total(store, start, end):
    """기간 합계. 담당: 기능 6"""
    raise NotImplementedError("기능 6 담당이 구현한다")


def category_of(e):
    """지출의 분류 이름. 분류가 없으면 규약의 "미분류". 담당: 기능 2

    규격: docs/공통모듈_함수규격.md 03
    - 앞뒤 공백을 지운 분류 이름. 키 없음·None·빈 문자열·공백뿐이면 "미분류"(rules.UNCATEGORIZED)
    - category_fixed 는 보지 않는다. 지출 원본은 바꾸지 않는다
    - e 가 dict 가 아님, category 가 str 도 None 도 아님 → ValueError
    """
    if not isinstance(e, dict):
        raise ValueError("지출은 dict여야 합니다")
    category = e.get("category")
    if category is None:
        return UNCATEGORIZED
    if not isinstance(category, str):
        raise ValueError(f"분류는 문자열이나 None이어야 합니다: {category!r}")
    name = category.strip()
    return name if name else UNCATEGORIZED


def category_totals(store, start, end):
    """분류별 건수와 금액. {분류: {"count": n, "amount": 원}} 담당: 기능 2"""
    raise NotImplementedError("기능 2 담당이 구현한다")


def person_paid(store, start, end):
    """사람마다 낸 돈 합계. 담당: 기능 3

    규격: docs/공통모듈_함수규격.md 06
    - 지출은 expenses_in(store, start, end) 로 고른다(삭제 제외, 양끝 포함)
    - {낸 사람: 금액 합}. key 순서는 expenses_in 결과에서 처음 나온 순서
    - 돈을 안 낸 회원은 넣지 않는다. 지출이 없으면 {}
    - expenses_in 의 ValueError 를 그대로 올리고, payer 가 비어 있지 않은 str 이 아니면 ValueError
    """
    totals = {}
    for e in expenses_in(store, start, end):
        payer = e.get("payer")
        if not isinstance(payer, str) or not payer.strip():
            raise ValueError(f"{e['id']}번 지출의 낸 사람이 잘못되었습니다: {payer!r}")
        totals[payer] = totals.get(payer, 0) + e["amount"]
    return totals


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
    """그날의 회원 이름 목록(명부 순서). 담당: 기능 5

    규격: docs/공통모듈_함수규격.md 16
    - 회원인지는 is_member_active 로만 판단한다(같은 기준)
    - 명부가 비어 있거나 그날 회원이 없으면 []
    - 날짜는 명부가 비어 있어도 먼저 검사한다. 잘못된 날짜·명부 자료는 ValueError
    """
    if on is None:
        raise ValueError("날짜가 비어 있습니다")
    day = dates.parse(on)
    roster = store.data.get("members")
    if not isinstance(roster, list):
        raise ValueError("명부(members)는 목록이어야 합니다")
    names = []
    for m in roster:
        if not isinstance(m, dict) or not isinstance(m.get("name"), str) or not m["name"].strip():
            raise ValueError(f"명부 자료 형식이 잘못되었습니다: {m!r}")
        names.append(m["name"])
    return [name for name in names if is_member_active(store, name, day)]


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
