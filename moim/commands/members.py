"""명령 묶음 `member`(참여자 명부). 담당: 기능 1(add·leave·list), 팀 공동 작업 설정 파일(load).

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from ..features import expenses

GROUP = 'member'


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="참여자 명부").add_subparsers(dest="cmd")

    s = grp.add_parser("add", help="회원 추가")
    s.add_argument("name")
    s.add_argument("joined")

    s = grp.add_parser("leave", help="회원 탈퇴일 기록")
    s.add_argument("name")
    s.add_argument("left")

    grp.add_parser("list", help="명부 목록")

    return grp


def run(c, args, cfg, store, out):
    if c == "add":
        m = expenses.add_member(store, args.name, args.joined)
        out(f"추가했습니다: {m['name']}(가입 {m['joined']})")
        return True

    if c == "leave":
        m = expenses.leave_member(store, args.name, args.left)
        out(f"탈퇴일을 적었습니다: {m['name']}(탈퇴 {m['left']})")
        return True

    if c == "list":
        items = expenses.list_members(store)
        if not items:
            out("회원이 없습니다")
        for m in items:
            out(f"{m['name']} 가입 {m['joined']} 탈퇴 {m['left'] or '-'}")
        return False

    out(f"아직 만들지 않은 명령입니다: {GROUP} {c or ''}".rstrip())
    return False
