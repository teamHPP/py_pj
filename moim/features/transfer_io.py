"""기능 6. 가져오기·내보내기.

이 기능을 구현하려면 아래 공통 함수를 이 기능 담당자가 채운다(공통 모듈 병합 요청으로).
  - common/ledger.py duplicates — 같은 날·같은 사람·같은 금액 지출 찾기(공용: 기능 1)
  - common/dates.py month_key — 날짜의 달 이름(공용: 기능 3)
  - common/queries.py period_total — 기간 합계(공용: 기능 3·5)
  - common/csvio.py detect_encoding, read_csv_rows — 인코딩 판별과 CSV 읽기(공용: 기능 5의 은행 거래내역 가져오기)

아래 함수의 이름과 인자는 바꾸지 않는다(인수 테스트와 채점이 이 이름으로 실행된다).
필요하면 함수를 더 만들어도 된다. 다른 기능 파일은 불러 쓰지 않는다.
"""

import csv
import copy
import json
import os
from ..common import cliutil, dates, ledger, money
from ..common.csvio import detect_encoding, read_csv_rows  # noqa: F401
from ..common.queries import active_members, category_of, expenses_in, period_total

# CSV 열 순서. 열 이름은 지출 필드 이름 그대로 써서 다시 읽을 때(read_csv_rows) 연결 없이 읽히게 한다.
CSV_FIELDS = ["id", "date", "payer", "amount", "members", "weights", "category", "memo"]


def _selected(store, start, end, category):
    """내보낼 지출: expenses_in 으로 기간을 고르고(삭제 제외), category 가 있으면 category_of 로 거른다.

    category 는 category_of 와 같은 방식으로 다듬는다(앞뒤 공백 제거, 빈 문자열은 "미분류").
    """
    if category is not None and not isinstance(category, str):
        raise ValueError(f"분류는 문자열이나 None이어야 합니다: {category!r}")
    items = expenses_in(store, start, end)
    if category is None:
        return items
    want = category_of({"category": category})
    return [e for e in items if category_of(e) == want]


def _summary(items):
    return len(items), sum(e["amount"] for e in items)


def _csv_row(e):
    weights = e.get("weights")
    return {
        "id": e["id"],
        "date": e["date"],
        "payer": e["payer"],
        "amount": e["amount"],
        "members": ";".join(e.get("members", [])),
        "weights": ";".join(f"{name}={w}" for name, w in weights.items()) if weights else "",
        "category": e.get("category") or "",
        "memo": e.get("memo", ""),
    }


def export_csv(store, path, start=None, end=None, category=None):
    """CSV 로 내보낸다(엑셀에서 한글이 깨지지 않게 UTF-8 BOM). 돌려주는 값: (건수, 합계)

    - 열: CSV_FIELDS. 참여자는 "김민수;이서연", 비율은 "김민수=2;이서연=1"(명령행 인자와 같은 형식)
    - 맞는 지출이 없어도 머리글만 있는 파일을 만들고 (0, 0)
    """
    items = _selected(store, start, end, category)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for e in items:
            w.writerow(_csv_row(e))
    return _summary(items)


def export_json(store, path, start=None, end=None, category=None):
    """JSON 으로 내보낸다(UTF-8, 한글 그대로). 지출 dict 목록을 그대로 쓴다. 돌려주는 값: (건수, 합계)"""
    items = _selected(store, start, end, category)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return _summary(items)


def _amount(value, where):
    """파일에서 읽은 금액 하나. 원 단위 정수가 아니거나 1원 미만이면 ValueError(위치 포함)."""
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{where}: 금액이 없거나 잘못되었습니다: {value!r}")
    try:
        amount = money.to_won(value)
    except ValueError:
        raise ValueError(f"{where}: 금액 형식이 잘못되었습니다: {value!r}") from None
    if amount < 1:
        raise ValueError(f"{where}: 금액은 1원 이상이어야 합니다: {value!r}")
    return amount


def _csv_amounts(path):
    _, rows = read_csv_rows(path)
    amounts = []
    for line, row in rows:
        if "amount" not in row:
            raise ValueError(f"CSV에 amount 열이 없습니다: {path}")
        if None in row or None in row.values():
            raise ValueError(f"{line}번 줄: 열 수가 머리글과 다릅니다")
        amounts.append(_amount(row["amount"], f"{line}번 줄"))
    return amounts


def _json_amounts(path):
    with open(path, encoding="utf-8-sig") as f:
        try:
            items = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON 형식이 잘못되었습니다: {exc}") from None
    if not isinstance(items, list):
        raise ValueError("JSON 파일은 지출 목록([...])이어야 합니다")
    amounts = []
    for i, e in enumerate(items, 1):
        if not isinstance(e, dict):
            raise ValueError(f"{i}번째 지출: 지출은 객체({{...}})여야 합니다")
        amounts.append(_amount(e.get("amount"), f"{i}번째 지출"))
    return amounts


def file_total(path):
    """내보낸 파일의 금액 합계와 건수.

    - 돌려주는 값: (합계, 건수)
    - 확장자가 .json 이면 JSON(export_json 형식), 아니면 CSV(export_csv 형식, read_csv_rows 로 읽음)
    - 머리글만 있는 CSV·빈 목록 JSON 은 (0, 0)
    - amount 열이 없음, 열 수가 다른 줄, 1원 미만이나 숫자가 아닌 금액, JSON 모양 오류는 ValueError(줄 번호 포함)
    - 파일이 없거나 읽을 수 없으면 OSError 그대로
    """
    if os.fspath(path).lower().endswith(".json"):
        amounts = _json_amounts(path)
    else:
        amounts = _csv_amounts(path)
    return sum(amounts), len(amounts)


def verify_export(store, path, start=None, end=None, category=None):
    """내보낸 파일 합계가 원래 기록 합계와 같은가. 돌려주는 값: (같은가, 파일 합계, 기록 합계)

    - 기록 합계는 공통 조회 함수로 센다: 분류를 고르지 않으면 period_total(19),
      분류를 고르면 규격 19 주의대로 expenses_in 결과를 category_of 로 걸러 더한다(_selected)
    """
    file_sum, _ = file_total(path)
    if category is None:
        total = period_total(store, start, end)
    else:
        _, total = _summary(_selected(store, start, end, category))
    return file_sum == total, file_sum, total


def export_count(store, start=None, end=None, category=None):
    """내보낼 때와 같은 기준으로 고른 기록의 건수(io verify 명령이 파일 건수와 함께 보여 준다)."""
    return len(_selected(store, start, end, category))


def roundtrip_check(store, path, start=None, end=None, category=None):
    """내보낸 파일을 다시 읽어 원래 기록과 똑같은지 대조. 다른 번호 목록을 돌려준다(비어 있으면 같음)."""
    raise NotImplementedError("이 함수를 구현한다")


IMPORT_REQUIRED = ("date", "payer", "amount")


def _import_row(store, row):
    """CSV 한 줄 → (date, payer, 원 금액, members, weights, memo, category). 잘못되면 이유를 담은 ValueError.

    - members 칸이 없거나 비어 있으면 그날의 회원 전원(규약 4, active_members)
    - members 는 "이름;이름2", weights 는 "이름=비율;…"(export_csv·명령행 인자와 같은 형식, cliutil 로 해석)
    - 빈 분류칸은 None(category_of 가 "미분류"로 읽는다)
    """
    if None in row or None in row.values():
        raise ValueError("열 수가 머리글과 다릅니다")
    day = dates.fmt(row["date"])
    payer = row["payer"].strip()
    members = cliutil._members(row.get("members") or "") or active_members(store, day)
    try:
        weights = cliutil._weights((row.get("weights") or "").strip())
    except ValueError:
        raise ValueError(f"비율 형식이 잘못되었습니다(이름=비율;…): {row.get('weights')!r}") from None
    day, amount = ledger.validate(store, day, payer, row["amount"], members, weights)
    category = (row.get("category") or "").strip() or None
    return day, payer, amount, members, weights, row.get("memo") or "", category


def import_csv(store, path, mapping=None, encoding=None, preview=False):
    """CSV 지출을 가져온다. 돌려주는 값: {"encoding", "added": [번호], "duplicates": [줄 번호], "errors": [(줄 번호, 오류)]}
    preview=True 면 실제로 넣지 않고 검사만 한다. 이때 added 에는 들어갈 줄 번호가 담긴다.

    - 읽기는 read_csv_rows(mapping: {파일 열 이름: 필드 이름}, 인코딩 판별 포함), 검사는 ledger.validate,
      넣기는 ledger.insert(action="import"). 지출 번호는 새로 매기고 파일의 id 열은 쓰지 않는다
    - 오류 줄은 건너뛰고 나머지는 넣는다. 파일에 date·payer·amount 열이 없으면 ValueError(아무것도 넣지 않음)
    """
    if preview:
        raise NotImplementedError("가져오기 미리 보기는 아직 구현 전입니다")
    used, rows = read_csv_rows(path, mapping, encoding)
    missing = [f for f in IMPORT_REQUIRED if rows and f not in rows[0][1]]
    if missing:
        raise ValueError(f"CSV에 필요한 열이 없습니다: {', '.join(missing)} (mapping 으로 열 이름을 연결하십시오)")
    result = {"encoding": used, "added": [], "duplicates": [], "errors": []}
    for line, row in rows:
        try:
            day, payer, amount, members, weights, memo, category = _import_row(store, row)
        except ValueError as exc:
            result["errors"].append((line, str(exc)))
            continue
        try:
            e = ledger.insert(store, day, payer, amount, members, memo, weights, category, action="import")
        except ValueError as exc:
            result["errors"].append((line, str(exc)))
            continue
        result["added"].append(e["id"])
    return result


def backup_all(store, path):
    raise NotImplementedError("이 함수를 구현한다")


def restore_all(store, path):
    raise NotImplementedError("이 함수를 구현한다")


def merge(store, other_path):
    """다른 모임 자료(백업 파일)의 회원·지출을 합친다. 지출 번호는 새로 매긴다. 돌려주는 값: 합친 지출 수"""
    raise NotImplementedError("이 함수를 구현한다")
