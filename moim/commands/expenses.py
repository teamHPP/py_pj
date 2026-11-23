"""명령 묶음 `exp`(지출 입력·관리). 담당: 기능 1.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from ..common import cliutil, money
from ..features import expenses

GROUP = 'exp'


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="지출 입력·관리").add_subparsers(dest="cmd")

    s = grp.add_parser("add", help="지출 추가")
    s.add_argument("date")
    s.add_argument("payer")
    s.add_argument("amount")
    s.add_argument("members", help="참여자, 예: 김민수;이서연")
    s.add_argument("--memo", default="")
    s.add_argument("--weights", help="비율, 예: 김민수=2;이서연=1")
    s.add_argument("--category")

    s = grp.add_parser("list", help="지출 목록")
    s.add_argument("--order", default="id", choices=["id", "date"])
    s.add_argument("--include-deleted", action="store_true")

    return grp


def run(c, args, cfg, store, out):
    if c == "add":
        members = cliutil._members(args.members)
        weights = cliutil._weights(args.weights)
        e, warnings = expenses.add_expense(store, args.date, args.payer, args.amount, members,
                                            memo=args.memo, weights=weights, category=args.category)
        for w in warnings:
            out(f"경고: {w}")
        out(f"추가했습니다: {e['id']}번 {e['date']} {e['payer']} {money.fmt(e['amount'])}원")
        return True

    if c == "list":
        items = expenses.list_expenses(store, order=args.order, include_deleted=args.include_deleted)
        if not items:
            out("지출이 없습니다")
        for e in items:
            mark = " (삭제됨)" if e.get("deleted") else ""
            out(f"{e['id']}번 {e['date']} {e['payer']} {money.fmt(e['amount'])}원{mark}")
        return False

    out(f"아직 만들지 않은 명령입니다: {GROUP} {c or ''}".rstrip())
    return False
