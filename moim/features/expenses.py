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


def add_member(store, name, joined):
    raise NotImplementedError("이 함수를 구현한다")


def leave_member(store, name, left):
    raise NotImplementedError("이 함수를 구현한다")


def load_members_file(store, path):
    """명부 파일을 읽어 명부에 반영한다. 한 줄 형식: 이름,가입일[,탈퇴일]. '#' 줄과 빈 줄은 건너뛴다.
    이미 있는 사람은 탈퇴일만 반영한다. 돌려주는 값: (추가한 이름, 탈퇴 반영한 이름, [(줄 번호, 오류)])"""
    raise NotImplementedError("이 함수를 구현한다")


def list_members(store):
    raise NotImplementedError("이 함수를 구현한다")


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
    raise NotImplementedError("이 함수를 구현한다")


def delete_expense(store, eid):
    """지출을 삭제 표시한다(지우지 않음). 확정 기간이면 거부한다."""
    raise NotImplementedError("이 함수를 구현한다")


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
