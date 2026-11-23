"""명령 묶음 `cat`(분류 규칙). 담당: 기능 2.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from ..common import cliutil, money
from ..features import categorize

GROUP = 'cat'


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="분류 규칙").add_subparsers(dest="cmd")

    s = grp.add_parser("add", help="분류 규칙 추가")
    s.add_argument("category")
    s.add_argument("--keywords", help="메모 키워드, 예: 저녁;회식")
    s.add_argument("--priority", type=int, default=0, help="클수록 먼저 적용(기본 0)")
    s.add_argument("--payer", help="낸 사람")
    s.add_argument("--min", dest="min_amount", help="최소 금액")
    s.add_argument("--max", dest="max_amount", help="최대 금액")

    s = grp.add_parser("remove", help="분류 규칙 삭제")
    s.add_argument("number", type=int, help="cat list 에 나온 규칙 번호")

    grp.add_parser("list", help="분류 규칙 목록")
    return grp


def _rules_path(cfg):
    return cfg.get("rules", "rules.json")


def _describe(rule):
    parts = []
    if rule.get("keywords"):
        parts.append("키워드 " + ", ".join(rule["keywords"]))
    if rule.get("payer"):
        parts.append(f"낸 사람 {rule['payer']}")
    if rule.get("min_amount") is not None or rule.get("max_amount") is not None:
        low = "" if rule.get("min_amount") is None else money.fmt(rule["min_amount"]) + "원"
        high = "" if rule.get("max_amount") is None else money.fmt(rule["max_amount"]) + "원"
        parts.append(f"금액 {low}~{high}")
    return f"{rule['category']} (우선순위 {rule.get('priority', 0)}) " + " / ".join(parts)


def run(c, args, cfg, store, out):
    path = _rules_path(cfg)

    if c == "add":
        rules = categorize.load_rules(path)
        keywords = cliutil._members(args.keywords) if args.keywords else None
        rule = categorize.add_rule(rules, args.category, keywords, args.priority, args.payer,
                                   args.min_amount, args.max_amount)
        categorize.save_rules(path, rules)
        out(f"규칙을 추가했습니다: {len(rules)}번 {_describe(rule)}")
        return False

    if c == "remove":
        rules = categorize.load_rules(path)
        rule = categorize.remove_rule(rules, args.number - 1)
        categorize.save_rules(path, rules)
        out(f"규칙을 삭제했습니다: {args.number}번 {_describe(rule)}")
        return False

    if c == "list":
        rules = categorize.load_rules(path)
        if not rules:
            out("분류 규칙이 없습니다")
        for i, rule in enumerate(rules, 1):
            out(f"{i}번 {_describe(rule)}")
        return False

    out(f"아직 만들지 않은 명령입니다: {GROUP} {c or ''}".rstrip())
    return False
