"""글자 표와 막대그래프. 보고서·지출 목록·정산·예산 명령이 함께 쓴다."""

import unicodedata

from . import money


def width(text):
    """화면 폭. 한글 등 넓은 글자는 2칸."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(text))


def pad(text, w, right=False):
    gap = w - width(text)
    return (" " * gap + str(text)) if right else (str(text) + " " * gap)


def _cell(value):
    """표 셀 하나를 글자로. int 는 천 단위 쉼표, str 은 그대로. 그 밖(bool·float·None 등)은 ValueError. (table 전용)"""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"표 셀은 str 이나 int 여야 합니다: {value!r}")
    return money.fmt(value) if isinstance(value, int) else value


def table(headers, rows, total=None, numeric=None):
    """표 문자열. numeric: 오른쪽 정렬할 열 번호 집합. 숫자는 천 단위 쉼표. 담당: 기능 3

    규격: docs/공통모듈_함수규격.md 07
    - numeric 열은 제목·자료 행·total 행 모두 오른쪽 정렬, 나머지 열은 왼쪽 정렬
    - 열 폭은 width 기준(한글 2칸)으로 headers·rows·total 중 가장 넓은 값
    - 셀 사이 공백 두 칸, 줄 끝 공백과 마지막 개행 없음
    - 구분선(열마다 열 폭만큼 '-', 공백 두 칸으로 이음)은 첫 자료 행 앞과 total 앞. rows 가 없으면 자료 행 앞 구분선도 없음
    - 빈 headers, str 이 아닌 제목, 열 수 불일치, 잘못된 열 번호, bool·float·None 셀은 ValueError
    """
    if not isinstance(headers, list) or not headers:
        raise ValueError("표 제목(headers)은 비어 있지 않은 목록이어야 합니다")
    if any(not isinstance(h, str) for h in headers):
        raise ValueError(f"표 제목은 str 이어야 합니다: {headers!r}")
    n = len(headers)
    if not isinstance(rows, list):
        raise ValueError("표의 행(rows)은 목록이어야 합니다")
    lines = [list(headers)]
    for row in rows:
        if not isinstance(row, list) or len(row) != n:
            raise ValueError("행의 열 수가 제목과 다릅니다")
        lines.append([_cell(v) for v in row])
    if total is not None:
        if not isinstance(total, list) or len(total) != n:
            raise ValueError("합계 행의 열 수가 제목과 다릅니다")
        lines.append([_cell(v) for v in total])
    if numeric is None:
        numeric = set()
    if not isinstance(numeric, (set, frozenset)):
        raise ValueError(f"numeric 은 열 번호의 set 이어야 합니다: {numeric!r}")
    for i in numeric:
        if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < n:
            raise ValueError(f"오른쪽 정렬할 열 번호가 잘못되었습니다(0~{n - 1}): {i!r}")

    widths = [max(width(line[i]) for line in lines) for i in range(n)]

    def render(line):
        return "  ".join(pad(c, widths[i], right=i in numeric) for i, c in enumerate(line)).rstrip()

    sep = "  ".join("-" * w for w in widths)
    out = [render(lines[0])]
    body = lines[1:1 + len(rows)]
    if body:
        out.append(sep)
        out.extend(render(line) for line in body)
    if total is not None:
        out.append(sep)
        out.append(render(lines[-1]))
    return "\n".join(out)


def bar_chart(data, bar_width=30, char="#"):
    """{이름: 값} 을 글자 막대그래프로. 담당: 기능 3

    규격: docs/공통모듈_함수규격.md 08
    - 막대 길이 = 값 × bar_width // 최댓값. 모든 값이 0이면 0칸(작은 값도 내림이라 0칸일 수 있음)
    - 한 줄 = 이름(가장 긴 이름 폭에 맞춰 왼쪽 정렬) + " | " + 막대 + " " + 천 단위 금액
    - dict 순서대로 '\\n' 으로 잇고 마지막 개행은 없다. {} 는 ""
    - dict 가 아님, str 이 아닌 key, 음수·bool·정수가 아닌 값, 0 이하·bool·정수가 아닌 bar_width,
      한 글자가 아니거나 폭 2칸·줄바꿈·제어문자인 char 는 ValueError
    """
    if not isinstance(data, dict):
        raise ValueError(f"막대그래프 자료는 dict 여야 합니다: {data!r}")
    for name, value in data.items():
        if not isinstance(name, str):
            raise ValueError(f"막대 이름은 str 이어야 합니다: {name!r}")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("막대 값은 0 이상의 정수여야 합니다")
    if isinstance(bar_width, bool) or not isinstance(bar_width, int) or bar_width <= 0:
        raise ValueError(f"막대 폭은 1 이상의 정수여야 합니다: {bar_width!r}")
    if (not isinstance(char, str) or len(char) != 1 or width(char) != 1
            or unicodedata.category(char).startswith("C")):
        raise ValueError(f"막대 글자는 화면 폭 1칸인 글자 하나여야 합니다: {char!r}")
    if not data:
        return ""

    top = max(data.values())
    name_w = max(width(name) for name in data)
    lines = []
    for name, value in data.items():
        bar = char * (value * bar_width // top) if top else ""
        lines.append(f"{pad(name, name_w)} | {bar} {money.fmt(value)}")
    return "\n".join(lines)
