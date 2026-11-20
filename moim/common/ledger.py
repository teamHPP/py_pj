"""지출 기록: 검사·추가·중복 찾기. 기능 1·6 담당이 채운다(각 함수 설명의 담당 참고)."""

import copy

from . import dates, money  # noqa: F401
from .queries import is_member_active, is_locked  # noqa: F401

# A2. insert 가 받는 action 값. 값을 늘릴 때는 공통 모듈 PR로만 한다.
INSERT_ACTIONS = ("add", "file_import", "recurring", "bank_import", "import", "merge")


def validate(store, date, payer, amount, members, weights=None):
    """지출 한 건을 검사한다. 통과하면 (date, 원 단위 금액)을 돌려주고, 아니면 이유를 담은 ValueError.
    담당: 기능 1"""
    if weights:
        # 비율 검사는 A1 money.check_weights(기능 4 담당, 2단계)에 맡긴다. 아직 없으므로 당분간 거부한다.
        raise NotImplementedError("비율(weights) 검사는 A1 money.check_weights(기능 4 담당)가 구현한다")

    try:
        amt = money.to_won(amount)
    except (ValueError, ArithmeticError) as exc:
        raise ValueError(f"금액 형식이 잘못되었습니다: {amount}") from exc
    if amt < 1:
        raise ValueError(f"지출 금액은 1원 이상이어야 합니다: {amt}")

    d = dates.fmt(date)

    if not members:
        raise ValueError("참여자가 비어 있습니다")
    if len(set(members)) != len(members):
        raise ValueError("참여자가 중복되었습니다")

    for name in [payer, *members]:
        if not is_member_active(store, name, d):
            raise ValueError(f"명부에 없거나 그날 회원이 아닙니다: {name}")

    if is_locked(store, d):
        raise ValueError(f"확정된 기간의 날짜라 지출을 넣을 수 없습니다: {d}")

    return d, amt


def duplicates(store, date, payer, amount, exclude_id=None):
    """같은 날·같은 금액·같은 사람의 지출 번호 목록(삭제된 것 제외). 담당: 기능 6"""
    raise NotImplementedError("기능 6 담당이 구현한다")


def insert(store, date, payer, amount, members, memo="", weights=None, category=None,
           recurring_id=None, action="add"):
    """검사 후 지출을 저장한다. 확정 기간이면 거부한다. 돌려주는 값: 새 지출(dict). 담당: 기능 1"""
    d, amt = validate(store, date, payer, amount, members, weights)

    if not isinstance(memo, str):
        raise ValueError("메모는 문자열이어야 합니다")
    if category is not None and not isinstance(category, str):
        raise ValueError("분류는 문자열이거나 없어야 합니다")
    if recurring_id is not None and (isinstance(recurring_id, bool) or not isinstance(recurring_id, int)
                                      or recurring_id <= 0):
        raise ValueError("반복 번호(recurring_id)는 양의 정수여야 합니다")
    if action not in INSERT_ACTIONS:
        raise ValueError(f"허용하지 않는 action입니다: {action}")

    eid = store.new_id()
    expense = {
        "id": eid,
        "date": d,
        "payer": payer,
        "amount": amt,
        "members": copy.deepcopy(list(members)),
        "memo": memo,
        "weights": copy.deepcopy(weights),
        "category": category,
        "deleted": False,
        "recurring_id": recurring_id,
    }
    store.data["expenses"].append(expense)
    store.record(action, eid, None, expense)
    return copy.deepcopy(expense)
