"""명령 묶음 `cat`(분류 규칙). 담당: 기능 2.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from ..common import cliutil, money, textfmt
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

    s = grp.add_parser("apply", help="규칙으로 전체 지출 다시 분류")
    s.add_argument("--preview", action="store_true", help="바꾸지 않고 바뀔 목록만 보기")

    grp.add_parser("uncat", help="분류되지 않은 지출 목록")

    s = grp.add_parser("set", help="분류 직접 지정(다시 분류해도 바뀌지 않게 고정)")
    s.add_argument("id", type=int, help="지출 번호")
    s.add_argument("category")

    s = grp.add_parser("unfix", help="직접 정한 분류의 고정 풀기")
    s.add_argument("id", type=int, help="지출 번호")

    period_args(grp.add_parser("summary", help="분류별 건수·금액"))
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
        if not 1 <= args.number <= len(rules):
            raise ValueError(f"없는 규칙 번호입니다: {args.number} (cat list로 번호를 확인하십시오)")
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

    if c == "apply":
        changes = categorize.apply_rules(store, categorize.load_rules(path), preview=args.preview)
        if not changes:
            out("바뀌는 지출이 없습니다")
        for eid, old, new in changes:
            out(f"{eid}번 {old} → {new}")
        if changes:
            out(f"{len(changes)}건을 {'바꿀 예정입니다(미리 보기)' if args.preview else '다시 분류했습니다'}")
        return bool(changes) and not args.preview

    if c == "uncat":
        items = categorize.uncategorized(store)
        if not items:
            out("분류되지 않은 지출이 없습니다")
        for e in items:
            out(f"{e['id']}번 {e['date']} {e['payer']} {money.fmt(e['amount'])}원 {e.get('memo') or ''}".rstrip())
        return False

    if c in ("set", "unfix"):
        old = store.get_expense(args.id)
        before = (old.get("category"), old.get("category_fixed", False))
        if c == "set":
            e = categorize.set_category(store, args.id, args.category)
            out(f"{e['id']}번 지출의 분류를 {e['category']}(으)로 정했습니다(다시 분류해도 바뀌지 않습니다)")
        else:
            e = categorize.unfix_category(store, args.id)
            out(f"{e['id']}번 지출의 분류 고정을 풀었습니다(다음 cat apply부터 규칙으로 다시 분류됩니다)")
        return (e.get("category"), e.get("category_fixed", False)) != before

    if c == "summary":
        start, end = cliutil._period(args)
        totals = categorize.summary(store, start, end)
        if not totals:
            out(f"{start} ~ {end} 기간에 지출이 없습니다")
            return False
        rows = [[name, v["count"], v["amount"]] for name, v in totals.items()]
        total = ["합계", sum(v["count"] for v in totals.values()), sum(v["amount"] for v in totals.values())]
        out(f"분류별 집계: {start} ~ {end}")
        out(textfmt.table(["분류", "건수", "금액"], rows, total=total, numeric={1, 2}))
        return False

    out(f"아직 만들지 않은 명령입니다: {GROUP} {c or ''}".rstrip())
    return False
