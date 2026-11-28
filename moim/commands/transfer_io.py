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
    _select_args(grp.add_parser("roundtrip", help="내보낸 파일을 다시 읽어 지출마다 원래 기록과 똑같은지 대조"
                                                   "(내보낼 때와 같은 기간·분류를 준다)"), period_args)
    s = grp.add_parser("import", help="CSV 지출 가져오기(UTF-8·CP949 자동 판별)")
    s.add_argument("path", help="CSV 파일 경로")
    s.add_argument("--map", default="", help="열 이름 연결 '파일 열=필드;…' 예: '날짜=date;금액=amount'")
    s.add_argument("--encoding", choices=["utf-8", "utf-8-sig", "cp949"], help="인코딩(안 주면 자동 판별)")
    s.add_argument("--preview", action="store_true", help="넣지 않고 들어갈 줄·중복·오류만 보기")
    s = grp.add_parser("merge", help="다른 모임 자료 파일(data.json 형식)의 회원·지출 합치기")
    s.add_argument("path", help="다른 모임의 자료 파일 경로")
    return grp


def _mapping(text):
    """'날짜=date;금액=amount' -> {'날짜': 'date', '금액': 'amount'}. 비어 있으면 None."""
    out = {}
    for part in filter(None, (p.strip() for p in text.split(";"))):
        col, sep, field = part.partition("=")
        if not sep or not col.strip() or not field.strip():
            raise ValueError(f"열 연결 형식이 잘못되었습니다('파일 열=필드'): {part}")
        out[col.strip()] = field.strip()
    return out or None


def _lines(nums):
    return ", ".join(str(n) for n in nums)


def run(c, args, cfg, store, out):
    if c == "merge":
        r = transfer_io.merge_detail(store, args.path)
        out(f"합쳤습니다: 지출 {len(r['added'])}건" + (f", 새 회원 {len(r['members'])}명" if r["members"] else ""))
        if r["duplicates"]:
            out(f"중복이라 건너뜀: 다른 모임의 {_lines(r['duplicates'])}번 지출")
        for where, why in r["errors"]:
            label = where if isinstance(where, str) else f"다른 모임의 {where}번 지출"
            out(f"오류({label}): {why}")
        return bool(r["added"] or r["members"])
    if c == "import":
        r = transfer_io.import_csv(store, args.path, _mapping(args.map), args.encoding, args.preview)
        if args.preview:
            out(f"미리 보기({r['encoding']}): 들어갈 줄 {len(r['added'])}개" +
                (f" - {_lines(r['added'])}번 줄" if r["added"] else "") + " (아직 넣지 않았습니다)")
        else:
            out(f"가져왔습니다({r['encoding']}): {len(r['added'])}건" +
                (f" - 지출 번호 {_lines(r['added'])}" if r["added"] else ""))
        if r["duplicates"]:
            out(f"중복이라 건너뜀: {_lines(r['duplicates'])}번 줄")
        for line, why in r["errors"]:
            out(f"오류 {line}번 줄: {why}")
        return bool(r["added"]) and not args.preview     # 미리 보기는 자료를 바꾸지 않으므로 저장 안 함
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
    if c == "roundtrip":
        start, end = _range(args)
        diff = transfer_io.roundtrip_check(store, args.path, start, end, args.category)
        if diff:
            out(f"원래 기록과 다른 지출 {len(diff)}건: {_lines(diff)}번")
        else:
            out(f"똑같습니다: 지출 {transfer_io.export_count(store, start, end, args.category)}건 모두 원래 기록과 같음")
        return False
    out(f"아직 만들지 않은 명령입니다: {GROUP} {c or ''}".rstrip())
    return False
