"""명령 묶음 `settle`(정산). 담당: 기능 4.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from ..common import cliutil, textfmt
from ..features import settle

GROUP = 'settle'


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="정산").add_subparsers(dest="cmd")
    s = grp.add_parser("show", help="기간 안 사람마다 낸 돈·부담할 돈·잔액")
    period_args(s)
    lk = grp.add_parser("lock", help="기간의 정산을 확정한다(잔액 합이 0일 때만)")
    period_args(lk)
    return grp


def run(c, args, cfg, store, out):
    if c == "show":
        start, end = cliutil._period(args)
        rows = settle.balances(store, start, end)
        if not rows:
            out(f"{start} ~ {end} 기간에 정산할 지출이 없습니다")
            return False
        keys = ("paid", "owed", "sent", "received", "balance")
        body = [[name, *(r[k] for k in keys)] for name, r in rows.items()]
        total = ["합계", *(sum(r[k] for r in rows.values()) for k in keys)]
        out(f"정산 기간: {start} ~ {end}")
        out(textfmt.table(["이름", "낸 돈", "부담할 돈", "보낸 송금", "받은 송금", "잔액"],
                          body, total=total, numeric={1, 2, 3, 4, 5}))
        s = settle.balance_sum(rows)
        out("잔액 합: 0 (정상) - 잔액이 양수면 받을 돈, 음수면 보낼 돈" if s == 0
            else f"잔액 합이 0이 아닙니다: {s:,}원 - 자료를 확인하십시오")
        return False
    if c == "lock":
        start, end = cliutil._period(args)
        lock = settle.lock_period(store, start, end)
        out(f"정산을 확정했습니다: {lock['start']} ~ {lock['end']}")
        out("이 기간의 지출은 이제 추가·수정·삭제·되살리기를 할 수 없습니다")
        return True
    out(f"아직 만들지 않은 명령입니다: {GROUP} {c or ''}".rstrip())
    return False
