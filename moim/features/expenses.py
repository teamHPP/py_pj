"""기능 1. 지출 입력·관리.

이 기능을 구현하려면 아래 공통 함수를 이 기능 담당자가 채운다(공통 모듈 병합 요청으로).
  - common/ledger.py validate — 지출 한 건 검사(공용: 기능 6의 가져오기 미리 보기)
  - common/ledger.py insert — 검사 후 저장(공용: 기능 4·5·6)

이 기능에 필요한 자료 항목은 common/store.py 의 EMPTY 에 이 기능 담당자가 추가한다.
  - 지출의 삭제 표시(deleted)
  - 수정·삭제 이력(history 목록과 Store.record)

아래 함수의 이름과 인자는 바꾸지 않는다(인수 테스트와 채점이 이 이름으로 실행된다).
필요하면 함수를 더 만들어도 된다. 다른 기능 파일은 불러 쓰지 않는다.
"""

import copy
import csv
from ..common import dates, ledger, money
from ..common.queries import is_locked

_EDITABLE_FIELDS = ("date", "payer", "amount", "members", "memo", "weights", "category")


def add_member(store, name, joined):
    """명부에 새 회원을 더한다(가입일부터, 탈퇴일 없음). 이미 있는 이름이면 거부한다. 돌려주는 값: 새 회원."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"이름이 비어 있습니다: {name!r}")
    name = name.strip()
    if store.member(name) is not None:
        raise ValueError(f"이미 명부에 있는 사람입니다: {name}")
    m = {"name": name, "joined": dates.fmt(joined), "left": None}
    store.data["members"].append(m)
    return copy.deepcopy(m)


def leave_member(store, name, left):
    """회원의 탈퇴일을 적는다. 탈퇴일은 그 사람의 가입일보다 앞일 수 없다. 돌려주는 값: 바뀐 회원."""
    m = store.member(name)
    if m is None:
        raise ValueError(f"명부에 없는 사람입니다: {name}")
    left_fmt = dates.fmt(left)
    if left_fmt < m["joined"]:
        raise ValueError(f"탈퇴일이 가입일보다 빠릅니다: {left_fmt} < {m['joined']}")
    m["left"] = left_fmt
    return copy.deepcopy(m)


def load_members_file(store, path):
    """명부 파일을 읽어 명부에 반영한다. 한 줄 형식: 이름,가입일[,탈퇴일]. '#' 줄과 빈 줄은 건너뛴다.
    이미 있는 사람은 탈퇴일만 반영한다. 돌려주는 값: (추가한 이름, 탈퇴 반영한 이름, [(줄 번호, 오류)])"""
    added, left_applied, errors = [], [], []
    with open(path, encoding="utf-8-sig") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) not in (2, 3) or not parts[0] or not parts[1]:
                errors.append((lineno, f"줄 형식이 잘못되었습니다(이름,가입일[,탈퇴일]): {line!r}"))
                continue
            name, joined = parts[0], parts[1]
            left = parts[2] if len(parts) == 3 and parts[2] else None
            try:
                if store.member(name) is None:
                    joined_fmt = dates.fmt(joined)
                    left_fmt = dates.fmt(left) if left is not None else None
                    if left_fmt is not None and left_fmt < joined_fmt:
                        raise ValueError(f"탈퇴일이 가입일보다 빠릅니다: {left_fmt} < {joined_fmt}")
                    store.data["members"].append({"name": name, "joined": joined_fmt, "left": left_fmt})
                    added.append(name)
                    if left_fmt is not None:
                        left_applied.append(name)
                elif left is not None:
                    leave_member(store, name, left)
                    left_applied.append(name)
            except ValueError as exc:
                errors.append((lineno, str(exc)))
    return added, left_applied, errors


def list_members(store):
    """명부 목록(명부 순서). 독립 복사본을 돌려준다."""
    return [copy.deepcopy(m) for m in store.data["members"]]


def add_expense(store, date, payer, amount, members, memo="", weights=None, category=None):
    """지출을 추가한다. 돌려주는 값: (지출, 경고 목록).

    먼저 ledger.duplicates 로 중복 의심을 찾아 경고 목록을 만들고(저장은 막지 않음),
    ledger.insert 로 검사 후 저장한다. 검사 실패 시 둘 다 아무것도 안 바뀐다.
    """
    dup_ids = ledger.duplicates(store, date, payer, amount)
    e = ledger.insert(store, date, payer, amount, members, memo=memo, weights=weights,
                       category=category, action="add")
    warnings = []
    if dup_ids:
        warnings.append(f"같은 날짜·낸 사람·금액의 지출이 이미 있습니다(번호: {dup_ids})")
    return e, warnings


def list_expenses(store, order="id", include_deleted=False):
    """지출 목록. order: "id"(번호순) 또는 "date"(날짜순, 같으면 번호순). 독립 복사본을 돌려준다."""
    if not isinstance(include_deleted, bool):
        raise ValueError(f"include_deleted는 True나 False여야 합니다: {include_deleted!r}")
    if order not in ("id", "date"):
        raise ValueError(f"정렬 기준이 잘못되었습니다(id 또는 date): {order!r}")
    items = store.data["expenses"]
    if not include_deleted:
        items = [e for e in items if not e.get("deleted", False)]
    key = (lambda e: e["id"]) if order == "id" else (lambda e: (e["date"], e["id"]))
    return [copy.deepcopy(e) for e in sorted(items, key=key)]


def edit_expense(store, eid, **changes):
    """지출을 고친다. 바꿀 수 있는 항목: date, payer, amount, members, memo, weights, category.

    바꾸기 전 날짜·바꾼 뒤 날짜 둘 다 확정 기간이면 거부한다(바꾼 뒤 날짜는 validate가 본다).
    """
    e = store.get_expense(eid)
    if e.get("deleted", False):
        raise ValueError(f"삭제된 지출은 수정할 수 없습니다: {eid}")
    unknown = set(changes) - set(_EDITABLE_FIELDS)
    if unknown:
        raise ValueError(f"고칠 수 없는 항목입니다: {sorted(unknown)}")
    if is_locked(store, e["date"]):
        raise ValueError(f"확정된 기간의 지출은 수정할 수 없습니다: {e['date']}")

    new_weights = changes.get("weights", e.get("weights"))
    d, amt = ledger.validate(store, changes.get("date", e["date"]), changes.get("payer", e["payer"]),
                              changes.get("amount", e["amount"]), changes.get("members", e["members"]),
                              new_weights)
    memo = changes.get("memo", e.get("memo", ""))
    if not isinstance(memo, str):
        raise ValueError("메모는 문자열이어야 합니다")
    category = changes.get("category", e.get("category"))
    if category is not None and not isinstance(category, str):
        raise ValueError("분류는 문자열이거나 없어야 합니다")

    before = copy.deepcopy(e)
    e["date"], e["payer"], e["amount"] = d, changes.get("payer", e["payer"]), amt
    e["members"] = copy.deepcopy(list(changes.get("members", e["members"])))
    e["memo"], e["weights"], e["category"] = memo, copy.deepcopy(new_weights), category
    store.record("edit", eid, before, copy.deepcopy(e))
    return copy.deepcopy(e)


def delete_expense(store, eid):
    """지출을 삭제 표시한다(지우지 않음). 확정 기간이면 거부한다."""
    e = store.get_expense(eid)
    if e.get("deleted", False):
        raise ValueError(f"이미 삭제된 지출입니다: {eid}")
    if is_locked(store, e["date"]):
        raise ValueError(f"확정된 기간의 지출은 삭제할 수 없습니다: {e['date']}")
    before = copy.deepcopy(e)
    e["deleted"] = True
    store.record("delete", eid, before, copy.deepcopy(e))
    return copy.deepcopy(e)


def restore_expense(store, eid):
    raise NotImplementedError("이 함수를 구현한다")


def undo_last_edit(store, eid):
    """그 지출의 가장 최근 수정(edit)을 되돌린다. 수정 이력의 바꾸기 전 값으로 돌려놓고, 되돌린 사실도 이력에 남긴다."""
    raise NotImplementedError("이 함수를 구현한다")


def history(store, eid=None):
    """수정·삭제 이력. eid 를 주면 그 지출의 이력만."""
    raise NotImplementedError("이 함수를 구현한다")


def add_from_file(store, path):
    """파일의 여러 줄을 한꺼번에 입력한다.

    한 줄 형식(쉼표 구분): 날짜,낸 사람,금액,참여자1;참여자2;...,메모
    '#' 로 시작하는 줄과 빈 줄은 건너뛴다. 돌려주는 값: (추가한 번호 목록, [(줄 번호, 오류)])
    """
    raise NotImplementedError("이 함수를 구현한다")
