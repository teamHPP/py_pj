"""명령 묶음 `io`(가져오기·내보내기). 담당: 기능 6.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from ..common import cliutil, money
from ..features import transfer_io

GROUP = 'io'


def _range(args):
    """--month 나 --start·--end 가 둘 다 있으면 cliutil._period, 아니면 주어진 쪽만 제한(없으면 전체)."""
    if args.month or (args.start and args.end):
        return cliutil._period(args)
    return args.start, args.end


def _select_args(s, period_args):
    s.add_argument("path", help="파일 경로")
    period_args(s)
    s.add_argument("--category", help="이 분류만(분류 없는 지출은 '미분류')")


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="가져오기·내보내기").add_subparsers(dest="cmd")
    _select_args(grp.add_parser("export-csv", help="지출을 CSV로 내보내기(엑셀용 UTF-8 BOM)"), period_args)
    _select_args(grp.add_parser("export-json", help="지출을 JSON으로 내보내기"), period_args)
    _select_args(grp.add_parser("verify", help="내보낸 파일 합계가 기록 합계와 같은지 검사"
                                                "(내보낼 때와 같은 기간·분류를 준다)"), period_args)
    return grp


def run(c, args, cfg, store, out):
    if c in ("export-csv", "export-json"):
        start, end = _range(args)
        fn = transfer_io.export_csv if c == "export-csv" else transfer_io.export_json
        count, total = fn(store, args.path, start, end, args.category)
        out(f"내보냈습니다: {args.path} ({count}건, 합계 {money.fmt(total)}원)")
        return False
    if c == "verify":
        start, end = _range(args)
        same, file_sum, total = transfer_io.verify_export(store, args.path, start, end, args.category)
        if same:
            out(f"일치합니다: 파일 합계 {money.fmt(file_sum)}원 = 기록 합계 {money.fmt(total)}원")
        else:
            out(f"일치하지 않습니다: 파일 합계 {money.fmt(file_sum)}원, 기록 합계 {money.fmt(total)}원"
                f" (차이 {money.fmt(file_sum - total)}원)")
        file_count = transfer_io.file_total(args.path)[1]
        count = transfer_io.export_count(store, start, end, args.category)
        if file_count != count:
            out(f"참고: 건수가 다릅니다(파일 {file_count}건, 기록 {count}건)")
        return False
    out(f"아직 만들지 않은 명령입니다: {GROUP} {c or ''}".rstrip())
    return False
