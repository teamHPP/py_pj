"""기능 2. 분류 규칙.

이 기능을 구현하려면 아래 공통 함수를 이 기능 담당자가 채운다(공통 모듈 병합 요청으로).
  - common/queries.py category_of — 지출의 분류 이름(공용: 기능 3·5·6)
  - common/queries.py category_totals — 분류별 건수·금액(공용: 기능 3·5)

이 기능에 필요한 자료 항목은 common/store.py 의 EMPTY 에 이 기능 담당자가 추가한다.
  - 직접 정한 분류의 고정 표시(category_fixed)

아래 함수의 이름과 인자는 바꾸지 않는다(인수 테스트와 채점이 이 이름으로 실행된다).
필요하면 함수를 더 만들어도 된다. 다른 기능 파일은 불러 쓰지 않는다.
"""

import json
import os
import tempfile
from ..common import money
from ..common.queries import category_totals


def _check_rules(rules):
    """규칙 목록 형식 검사. 잘못되면 ValueError."""
    if not isinstance(rules, list):
        raise ValueError("규칙 목록은 list여야 합니다")
    for i, rule in enumerate(rules, 1):
        if not isinstance(rule, dict) or not isinstance(rule.get("category"), str):
            raise ValueError(f"{i}번 규칙의 형식이 잘못되었습니다: {rule!r}")


def load_rules(path):
    """규칙 파일(JSON)을 읽어 규칙 목록을 돌려준다. 파일이 아직 없으면 []."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
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
    raise NotImplementedError("이 함수를 구현한다")


def classify(e, rules):
    """맞는 규칙 가운데 우선순위가 가장 높은 규칙의 분류. 같으면 먼저 등록한 규칙. 없으면 None."""
    raise NotImplementedError("이 함수를 구현한다")


def apply_rules(store, rules, preview=False):
    """전체 지출을 다시 분류한다. 직접 정한 분류(고정)는 건너뛴다.
    돌려주는 값: 바뀌는 목록 [(번호, 이전 분류, 새 분류)]. preview=True 면 실제로 바꾸지 않는다."""
    raise NotImplementedError("이 함수를 구현한다")


def set_category(store, eid, category):
    """분류를 직접 정한다. 다시 분류해도 바뀌지 않게 고정한다."""
    raise NotImplementedError("이 함수를 구현한다")


def unfix_category(store, eid):
    raise NotImplementedError("이 함수를 구현한다")


def uncategorized(store):
    raise NotImplementedError("이 함수를 구현한다")


def overlaps(rules):
    """같은 키워드가 서로 다른 분류의 규칙에 함께 있는 경우. [(규칙 번호 i, 규칙 번호 j, 겹친 키워드)]"""
    raise NotImplementedError("이 함수를 구현한다")


def summary(store, start, end):
    """분류별 건수·금액(공통 모듈의 분류 조회 사용)."""
    raise NotImplementedError("이 함수를 구현한다")
