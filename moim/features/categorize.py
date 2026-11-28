"""기능 2. 분류 규칙.

이 기능을 구현하려면 아래 공통 함수를 이 기능 담당자가 채운다(공통 모듈 병합 요청으로).
  - common/queries.py category_of — 지출의 분류 이름(공용: 기능 3·5·6)
  - common/queries.py category_totals — 분류별 건수·금액(공용: 기능 3·5)

이 기능에 필요한 자료 항목은 common/store.py 의 EMPTY 에 이 기능 담당자가 추가한다.
  - 직접 정한 분류의 고정 표시(category_fixed)

아래 함수의 이름과 인자는 바꾸지 않는다(인수 테스트와 채점이 이 이름으로 실행된다).
필요하면 함수를 더 만들어도 된다. 다른 기능 파일은 불러 쓰지 않는다.
"""

import copy
import json
import os
import tempfile
from ..common import money
from ..common.queries import category_of, category_totals, expenses_in, is_locked
from ..common.rules import UNCATEGORIZED


def _is_amount(value):
    return value is None or (isinstance(value, int) and not isinstance(value, bool) and value >= 0)


def _rule_ok(rule):
    """규칙 하나가 add_rule 이 만드는 모양과 같은 기준을 지키는가."""
    if not isinstance(rule, dict):
        return False
    category, keywords = rule.get("category"), rule.get("keywords", [])
    priority, payer = rule.get("priority", 0), rule.get("payer")
    low, high = rule.get("min_amount"), rule.get("max_amount")
    if not isinstance(category, str) or not category.strip():
        return False
    if not isinstance(keywords, list) or not all(isinstance(w, str) and w.strip() for w in keywords):
        return False
    if isinstance(priority, bool) or not isinstance(priority, int):
        return False
    if payer is not None and (not isinstance(payer, str) or not payer.strip()):
        return False
    if not _is_amount(low) or not _is_amount(high):
        return False
    if low is not None and high is not None and low > high:
        return False
    return bool(keywords) or payer is not None or low is not None or high is not None


def _check_rules(rules):
    """규칙 목록 형식 검사(add_rule 과 같은 기준). 잘못되면 ValueError."""
    if not isinstance(rules, list):
        raise ValueError("규칙 목록은 list여야 합니다")
    for i, rule in enumerate(rules, 1):
        if not _rule_ok(rule):
            raise ValueError(f"{i}번 규칙의 형식이 잘못되었습니다: {rule!r}")


def load_rules(path):
    """규칙 파일(JSON)을 읽어 규칙 목록을 돌려준다. 파일이 아직 없으면 []."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:   # 메모장 등이 붙인 BOM 이 있어도 읽는다
        try:
            rules = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"규칙 파일이 올바른 JSON이 아닙니다: {path} ({exc})") from None
    _check_rules(rules)
    return rules


def save_rules(path, rules):
    """규칙 목록을 JSON 파일로 저장한다. 임시 파일에 쓴 뒤 바꿔 끼워 저장 도중 멈춰도 파일이 깨지지 않는다."""
    _check_rules(rules)
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".rules-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _amount_or_none(value, label):
    if value is None:
        return None
    amount = money.to_won(value)
    if amount < 0:
        raise ValueError(f"{label}은 0원 이상이어야 합니다: {value}")
    return amount


def add_rule(rules, category, keywords=None, priority=0, payer=None, min_amount=None, max_amount=None):
    """규칙 하나를 목록 끝에 더하고 그 규칙을 돌려준다. 목록 순서가 곧 등록 순서다."""
    if not isinstance(rules, list):
        raise ValueError("규칙 목록은 list여야 합니다")
    if not isinstance(category, str) or not category.strip():
        raise ValueError("분류 이름을 입력하십시오")
    if keywords is None:
        keywords = []
    if isinstance(keywords, str) or not isinstance(keywords, (list, tuple)):
        raise ValueError(f"키워드는 문자열 목록이어야 합니다: {keywords!r}")
    words = []
    for word in keywords:
        if not isinstance(word, str):
            raise ValueError(f"키워드는 문자열이어야 합니다: {word!r}")
        if word.strip() and word.strip() not in words:
            words.append(word.strip())
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(f"우선순위는 정수여야 합니다: {priority!r}")
    if payer is not None and (not isinstance(payer, str) or not payer.strip()):
        raise ValueError(f"낸 사람이 잘못되었습니다: {payer!r}")
    low = _amount_or_none(min_amount, "최소 금액")
    high = _amount_or_none(max_amount, "최대 금액")
    if low is not None and high is not None and low > high:
        raise ValueError(f"최소 금액이 최대 금액보다 큽니다: {low} > {high}")
    if not words and payer is None and low is None and high is None:
        raise ValueError("규칙에 조건(키워드, 낸 사람, 금액 범위)이 하나 이상 있어야 합니다")
    rule = {"category": category.strip(), "keywords": words, "priority": priority,
            "payer": None if payer is None else payer.strip(), "min_amount": low, "max_amount": high}
    rules.append(rule)
    return rule


def remove_rule(rules, index):
    """index 번째(0부터) 규칙을 지우고 지운 규칙을 돌려준다."""
    if not isinstance(rules, list):
        raise ValueError("규칙 목록은 list여야 합니다")
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(rules):
        raise ValueError(f"없는 규칙 번호입니다: {index!r}")
    return rules.pop(index)


def matches(rule, e):
    """규칙의 조건을 모두 만족하는가. 키워드는 하나라도 메모에 있으면 만족."""
    if not _rule_ok(rule):
        raise ValueError(f"규칙의 형식이 잘못되었습니다: {rule!r}")
    if not isinstance(e, dict):
        raise ValueError("지출은 dict여야 합니다")
    memo = e.get("memo")
    if memo is None:
        memo = ""
    if not isinstance(memo, str):
        raise ValueError(f"{e.get('id', '?')}번 지출의 메모가 잘못되었습니다: {memo!r}")
    keywords = rule.get("keywords", [])
    if keywords and not any(word.strip() in memo for word in keywords):
        return False
    if rule.get("payer") is not None and e.get("payer") != rule["payer"].strip():
        return False
    low, high = rule.get("min_amount"), rule.get("max_amount")
    if low is not None or high is not None:
        amount = e.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise ValueError(f"{e.get('id', '?')}번 지출의 금액이 잘못되었습니다: {amount!r}")
        if (low is not None and amount < low) or (high is not None and amount > high):
            return False
    return True


def classify(e, rules):
    """맞는 규칙 가운데 우선순위가 가장 높은 규칙의 분류. 같으면 먼저 등록한 규칙. 없으면 None."""
    _check_rules(rules)
    best = None
    for rule in rules:   # 목록 순서가 등록 순서. 우선순위가 더 클 때만 바꾸므로 같으면 먼저 등록한 규칙이 남는다
        if matches(rule, e) and (best is None or rule.get("priority", 0) > best.get("priority", 0)):
            best = rule
    return None if best is None else best["category"].strip()


def apply_rules(store, rules, preview=False):
    """전체 지출을 다시 분류한다. 직접 정한 분류(고정)는 건너뛴다.
    돌려주는 값: 바뀌는 목록 [(번호, 이전 분류, 새 분류)]. preview=True 면 실제로 바꾸지 않는다."""
    _check_rules(rules)
    if not isinstance(preview, bool):
        raise ValueError(f"preview 는 True 나 False 여야 합니다: {preview!r}")
    items = store.data.get("expenses")
    if not isinstance(items, list):
        raise ValueError("지출 목록 형식이 잘못되었습니다")

    # 먼저 모두 계산하고 나서 바꾼다. 중간에 오류가 나면 아무것도 바뀌지 않는다.
    planned = []
    for e in items:
        if not isinstance(e, dict):
            raise ValueError(f"지출 자료 형식이 잘못되었습니다: {e!r}")
        if e.get("deleted", False) or e.get("category_fixed", False):
            continue   # 삭제된 지출, 직접 정한 분류(고정)는 건너뛴다
        if is_locked(store, e.get("date")):
            continue   # 규약 6: 확정한 기간의 지출은 수정하지 않는다
        new = classify(e, rules)
        old = category_of(e)
        if new is not None and new != old:   # 맞는 규칙이 없으면 지금 분류를 그대로 둔다
            planned.append((e, old, new))

    if not preview:
        for e, _, new in planned:
            before = copy.deepcopy(e)
            e["category"] = new
            store.record("edit", e["id"], before, copy.deepcopy(e))
    return [(e["id"], old, new) for e, old, new in planned]


def set_category(store, eid, category):
    """분류를 직접 정한다. 다시 분류해도 바뀌지 않게 고정한다."""
    if not isinstance(category, str) or not category.strip():
        raise ValueError("분류 이름을 입력하십시오")
    e = _changeable(store, eid)
    name = category.strip()
    if e.get("category") == name and e.get("category_fixed", False):
        return copy.deepcopy(e)   # 이미 같은 분류로 고정되어 있으면 바꾸지 않는다
    before = copy.deepcopy(e)
    e["category"], e["category_fixed"] = name, True
    store.record("edit", e["id"], before, copy.deepcopy(e))
    return copy.deepcopy(e)


def unfix_category(store, eid):
    """직접 정한 분류의 고정을 푼다. 분류 이름은 그대로 두고, 다음 다시 분류부터 규칙이 적용된다."""
    e = _changeable(store, eid)
    if not e.get("category_fixed", False):
        return copy.deepcopy(e)   # 고정되어 있지 않으면 바꾸지 않는다
    before = copy.deepcopy(e)
    e["category_fixed"] = False
    store.record("edit", e["id"], before, copy.deepcopy(e))
    return copy.deepcopy(e)


def _changeable(store, eid):
    """분류를 바꿀 수 있는 지출 원본. 없는 번호·삭제된 지출·확정된 기간의 지출은 ValueError."""
    if isinstance(eid, bool):
        raise ValueError(f"지출 번호가 잘못되었습니다: {eid!r}")
    e = store.get_expense(eid)
    if e.get("deleted", False):
        raise ValueError(f"삭제된 지출은 분류를 바꿀 수 없습니다: {eid}")
    if is_locked(store, e["date"]):
        raise ValueError(f"확정된 기간의 지출은 분류를 바꿀 수 없습니다: {e['date']}")
    return e


def uncategorized(store):
    """분류가 없는("미분류") 지출 목록. 삭제된 지출은 빼고 (날짜, 번호) 순서의 복사본으로 돌려준다."""
    return [e for e in expenses_in(store, None, None) if category_of(e) == UNCATEGORIZED]


def overlaps(rules):
    """같은 키워드가 서로 다른 분류의 규칙에 함께 있는 경우. [(규칙 번호 i, 규칙 번호 j, 겹친 키워드)]
    번호는 remove_rule 과 같이 0부터 센 목록 위치이고 i < j. (i, j) 순서, 키워드는 규칙 i 에 적힌 순서."""
    _check_rules(rules)
    found = []
    for i, first in enumerate(rules):
        for j in range(i + 1, len(rules)):
            second = rules[j]
            if first["category"].strip() == second["category"].strip():
                continue   # 같은 분류끼리는 겹쳐도 분류 결과가 같다
            others = {w.strip() for w in second.get("keywords", [])}
            for word in first.get("keywords", []):
                if word.strip() in others:
                    found.append((i, j, word.strip()))
    return found


def summary(store, start, end):
    """분류별 건수·금액(공통 모듈의 분류 조회 사용).
    {분류: {"count": n, "amount": 원}}. 지출 고르기·분류 이름·순서·오류는 queries.category_totals(04)를 그대로 따른다."""
    return category_totals(store, start, end)
