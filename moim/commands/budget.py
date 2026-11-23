"""명령 묶음 `budget`(예산·회비). 담당: 기능 5.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.

하위 명령
  budget status  [--month YYYY-MM]                          그달 예산·지출·남은 금액(없으면 이번 달)
  budget pay     이름 금액 [--date YYYY-MM-DD] [--memo 메모]    회비 입금 기록(날짜가 없으면 오늘)
  budget balance [--until YYYY-MM-DD]                        모임 통장 잔고(없으면 전체)
"""

from ..common import dates, money
from ..features import budget

GROUP = 'budget'


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="예산·회비").add_subparsers(dest="cmd")

    s = grp.add_parser("status", help="그달 예산 초과 여부와 남은 금액")
    s.add_argument("--month", help="YYYY-MM (없으면 이번 달)")

    s = grp.add_parser("pay", help="회비 입금 기록")
    s.add_argument("member", help="입금한 사람(명부에 있는 이름)")
    s.add_argument("amount", help="금액(원), 예: 20,000")
    s.add_argument("--date", help="입금한 날짜 YYYY-MM-DD (없으면 오늘)")
    s.add_argument("--memo", default="")

    s = grp.add_parser("balance", help="모임 통장 잔고(회비 입금 합계 - 지출 합계)")
    s.add_argument("--until", help="이날까지 YYYY-MM-DD (없으면 전체)")
    return grp


def run(c, args, cfg, store, out):
    if c == "status":
        month = args.month or dates.month_key(dates.today())
        s = budget.month_status(store, cfg, month)
        out(f"{s['month']} 예산 {money.fmt(s['budget'])}원 / 지출 {money.fmt(s['spent'])}원")
        if s["over"]:
            out(f"예산을 {money.fmt(-s['remaining'])}원 넘었습니다")
        else:
            out(f"남은 금액: {money.fmt(s['remaining'])}원")
        return False

    if c == "pay":
        p = budget.record_payment(store, args.date or dates.today(), args.member, args.amount, args.memo)
        out(f"회비 입금을 기록했습니다: {p['id']}번 {p['date']} {p['member']} {money.fmt(p['amount'])}원")
        return True

    if c == "balance":
        total = budget.treasury_balance(store, args.until)
        label = f"{dates.fmt(args.until)}까지 " if args.until else ""
        out(f"{label}모임 통장 잔고: {money.fmt(total)}원")
        return False

    out(f"아직 만들지 않은 명령입니다: {GROUP} {c or ''}".rstrip())
    return False
