"""명령 묶음 `report`(월별·기간 보고서). 담당: 기능 3.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from ..common import cliutil
from ..features import report

GROUP = 'report'


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="보고서").add_subparsers(dest="cmd")

    s = grp.add_parser("month", help="한 달 보고서(합계·분류별·사람별)")
    s.add_argument("month", help="YYYY-MM")

    s = grp.add_parser("period", help="기간 보고서(합계·분류별·사람별)")
    period_args(s)

    s = grp.add_parser("months", help="여러 달의 월별 합계")
    s.add_argument("start_month", help="시작 달 YYYY-MM")
    s.add_argument("end_month", help="끝 달 YYYY-MM")

    return grp


def run(c, args, cfg, store, out):
    if c == "month":
        out(report.month_report(store, args.month))
        return False

    if c == "period":
        start, end = cliutil._period(args)
        out(report.period_report(store, start, end))
        return False

    if c == "months":
        out(report.monthly_report(store, args.start_month, args.end_month))
        return False

    out(f"아직 만들지 않은 명령입니다: {GROUP} {c or ''}".rstrip())
    return False
