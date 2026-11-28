"""기능 4. 정산.

이 기능을 구현하려면 아래 공통 함수를 이 기능 담당자가 채운다(공통 모듈 병합 요청으로).
  - common/money.py split 의 비율 분배 부분(공용: 기능 5의 회비 차감)
  - common/queries.py expense_shares, member_shares — 지출별·사람별 부담액(공용: 기능 5)
  - common/queries.py is_locked — 확정 기간인가(공용: 기능 1·6)

이 기능에 필요한 자료 항목은 common/store.py 의 EMPTY 에 이 기능 담당자가 추가한다.
  - 사람별 비율(weights)
  - 송금 기록(transfers 목록)
  - 확정 기간(locks 목록)
  - 반복 지출(recurring 목록)

아래 함수의 이름과 인자는 바꾸지 않는다(인수 테스트와 채점이 이 이름으로 실행된다).
필요하면 함수를 더 만들어도 된다. 다른 기능 파일은 불러 쓰지 않는다.
"""

import copy
from ..common import dates, ledger, money
from ..common.queries import expense_shares, expenses_in, is_locked, member_shares, person_paid


def _transfers_in(store, start, end):
    """기간 안의 송금 기록을 (보낸 사람, 받은 사람, 금액)으로 돌려준다. 기간은 양끝 포함, None 이면 제한 없음."""
    items = store.data.get("transfers", [])
    if not isinstance(items, list):
        raise ValueError("송금 기록(transfers)은 목록이어야 합니다")
    first = None if start is None else dates.parse(start)
    last = None if end is None else dates.parse(end)
    picked = []
    for t in items:
        if not isinstance(t, dict) or any(k not in t for k in ("date", "from", "to", "amount")):
            raise ValueError(f"송금 기록 형식이 잘못되었습니다(date·from·to·amount 필요): {t!r}")
        amount = t["amount"]
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 1:
            raise ValueError(f"송금 금액이 잘못되었습니다(1원 이상의 정수): {amount!r}")
        day = dates.parse(t["date"])
        if dates.in_period(day, day if first is None else first, day if last is None else last):
            picked.append((t["from"], t["to"], amount))
    return picked


def balances(store, start, end):
    """사람마다 낸 돈, 부담할 돈, 이미 보낸·받은 송금, 잔액.
    잔액 = 낸 돈 - 부담할 돈 + 보낸 송금 - 받은 송금. 양수면 받을 돈, 음수면 보낼 돈.

    돌려주는 값: {이름: {"paid", "owed", "sent", "received", "balance"}} (모두 원 단위 int).
    낸 돈은 person_paid, 부담할 돈은 member_shares(나머지 1원은 split 규약)로 계산하고, 둘 다 expenses_in 의
    기간(양끝 포함)·삭제 제외를 따른다. 정산에 나온 사람만 넣는다(순서: 부담할 돈 → 낸 돈 → 송금에 처음 나온 순서).
    """
    paid = person_paid(store, start, end)
    owed = member_shares(store, start, end)
    moves = _transfers_in(store, start, end)
    names = list(dict.fromkeys([*owed, *paid, *(n for f, t, _ in moves for n in (f, t))]))
    rows = {n: {"paid": paid.get(n, 0), "owed": owed.get(n, 0), "sent": 0, "received": 0} for n in names}
    for frm, to, amount in moves:
        rows[frm]["sent"] += amount
        rows[to]["received"] += amount
    for r in rows.values():
        r["balance"] = r["paid"] - r["owed"] + r["sent"] - r["received"]
    return rows


def balance_sum(rows):
    """모든 사람 잔액의 합. 규칙대로라면 항상 0이다."""
    if not isinstance(rows, dict):
        raise ValueError(f"정산 결과는 {{이름: 행}} 형식이어야 합니다: {rows!r}")
    return sum(r["balance"] for r in rows.values())


def minimal_transfers(rows):
    """송금 횟수를 줄인 '누가 누구에게 얼마' 목록. 가장 많이 보낼 사람이 가장 많이 받을 사람에게 보내는 방식."""
    raise NotImplementedError("이 함수를 구현한다")


def record_transfer(store, date, frm, to, amount):
    """이미 보낸 송금을 기록한다(부분 정산)."""
    raise NotImplementedError("이 함수를 구현한다")


def lock_period(store, start, end):
    """정산을 확정한다. 이 기간의 지출은 더 이상 추가·수정·삭제할 수 없다.

    기간(시작일·끝일 포함)의 잔액 합이 0일 때만 store.data["locks"] 끝에 {"start", "end"}(YYYY-MM-DD)를
    더하고, 더한 기간을 돌려준다. 시작일이 끝일보다 늦거나, 이미 확정된 한 기간 안에 모두 들어가거나,
    잔액 합이 0이 아니면 ValueError 를 내고 자료를 바꾸지 않는다. 디스크 저장은 명령 쪽이 한다.
    """
    first, last = dates.parse(start), dates.parse(end)
    if first > last:
        raise ValueError(f"시작일이 끝일보다 늦습니다: {dates.fmt(first)} ~ {dates.fmt(last)}")
    locks = store.data.get("locks", [])
    if not isinstance(locks, list):
        raise ValueError("확정 기간(locks)은 목록이어야 합니다")
    for lock in locks:
        if not isinstance(lock, dict) or "start" not in lock or "end" not in lock:
            raise ValueError(f"확정 기간 형식이 잘못되었습니다(start·end 필요): {lock!r}")
        if dates.parse(lock["start"]) <= first and last <= dates.parse(lock["end"]):
            raise ValueError(f"이미 확정된 기간입니다: {lock['start']} ~ {lock['end']}")
    total = balance_sum(balances(store, first, last))
    if total != 0:
        raise ValueError(f"잔액 합이 0이 아니어서 확정할 수 없습니다: {total:,}원")
    new = {"start": dates.fmt(first), "end": dates.fmt(last)}
    store.data["locks"] = locks
    locks.append(new)
    return dict(new)


def statement(store, start, end, person):
    """정산 내역서: 그 사람이 어떤 지출에 얼마를 부담했는지. [(날짜, 번호, 메모, 지출 금액, 내 부담액)]"""
    raise NotImplementedError("이 함수를 구현한다")


def exclude_member(store, eid, name):
    """특정 지출에서 특정 사람을 뺀다(그 사람 몫을 남은 사람이 나눈다)."""
    raise NotImplementedError("이 함수를 구현한다")


def compare(old_rows, new_rows):
    """이전 정산과 비교: {이름: (이전 잔액, 지금 잔액, 차이)}"""
    raise NotImplementedError("이 함수를 구현한다")


def add_recurring(store, day, payer, amount, members, memo, start_month):
    raise NotImplementedError("이 함수를 구현한다")


def run_recurring(store, until):
    """until 날짜까지 아직 만들지 않은 반복 지출을 만든다. 달 말일보다 큰 날은 말일로. 돌려주는 값: 만든 지출 목록."""
    raise NotImplementedError("이 함수를 구현한다")
