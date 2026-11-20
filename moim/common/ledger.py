"""지출 기록: 검사·추가·중복 찾기. 기능 1·6 담당이 채운다(각 함수 설명의 담당 참고)."""

from . import dates, money  # noqa: F401
from .queries import is_member_active, is_locked  # noqa: F401


def validate(store, date, payer, amount, members, weights=None):
    """지출 한 건을 검사한다. 통과하면 (date, 원 단위 금액)을 돌려주고, 아니면 이유를 담은 ValueError.
    담당: 기능 1"""
    raise NotImplementedError("기능 1 담당이 구현한다")


def duplicates(store, date, payer, amount, exclude_id=None):
    """같은 날·같은 금액·같은 사람의 지출 번호 목록(삭제된 것 제외). 담당: 기능 6

    찾기만 한다. 명부·회원 여부·잠금은 검사하지 않고, Store도 바꾸지 않는다.
    돌려주는 값: 조건이 맞고 삭제되지 않은 지출 번호, 오름차순. 맞는 것이 없으면 [].
    0원 이하 금액도 거부하지 않고 [](1원 이상 검사는 validate 한 곳에서만 한다).
    """
    day = dates.fmt(date)   # 잘못된 날짜는 dates.fmt 의 ValueError 그대로
    # validate 와 같은 문구를 쓰도록 to_won 예외를 감싼다(to_won 은 채점 때 정상판으로 바뀔 수 있다)
    if isinstance(amount, bool):
        raise ValueError(f"금액 형식이 잘못되었습니다: {amount}")
    try:
        won = money.to_won(amount)
    except (ValueError, ArithmeticError):
        raise ValueError(f"금액 형식이 잘못되었습니다: {amount}") from None
    if exclude_id is not None and (isinstance(exclude_id, bool) or not isinstance(exclude_id, int)
                                   or exclude_id <= 0):
        raise ValueError("제외 번호는 양의 정수여야 합니다")
    found = []
    for e in store.data["expenses"]:
        if e.get("deleted", False) or e["id"] == exclude_id:
            continue
        if e["date"] == day and e["payer"] == payer and e["amount"] == won:
            found.append(e["id"])
    return sorted(found)


def insert(store, date, payer, amount, members, memo="", weights=None, category=None,
           recurring_id=None, action="add"):
    """검사 후 지출을 저장한다. 확정 기간이면 거부한다. 돌려주는 값: 새 지출(dict). 담당: 기능 1"""
    raise NotImplementedError("기능 1 담당이 구현한다")
