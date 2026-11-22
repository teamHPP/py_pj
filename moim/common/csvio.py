"""CSV 읽기: 글자 인코딩 판별(UTF-8·CP949)과 열 이름 연결. 가져오기(기능 6)와 은행 거래내역 가져오기(기능 5)가 함께 쓴다."""

import csv


def detect_encoding(path):
    """UTF-8(BOM 포함)로 읽히면 utf-8-sig, 아니면 cp949. 둘 다 안 되면 ValueError.

    규격: docs/공통모듈_함수규격.md 21
    - 파일 전체를 바이트로 읽어 UTF-8(BOM 허용)로 먼저, 안 되면 CP949로 엄격하게(strict) 풀어 본다
    - 영문·숫자만 있어 둘 다 되는 파일과 0바이트 파일은 "utf-8-sig". 파일은 바꾸지 않는다
    - 파일이 없거나 읽을 수 없으면 OSError 를 그대로 올린다
    """
    with open(path, "rb") as f:
        raw = f.read()
    for encoding in ("utf-8-sig", "cp949"):
        try:
            raw.decode(encoding, "strict")
        except UnicodeDecodeError:
            continue
        return encoding
    raise ValueError(f"UTF-8 또는 CP949로 읽을 수 없습니다: {path}")


def read_csv_rows(path, mapping=None, encoding=None):
    """CSV 를 읽어 (인코딩, [(줄 번호, {필드: 값})]) 를 돌려준다. mapping: {파일 열 이름: 필드 이름}

    규격: docs/공통모듈_함수규격.md 22
    - encoding 이 None 이면 detect_encoding 으로 정한다. "utf-8"·"utf-8-sig"·"cp949" 만 받는다.
      UTF-8 계열은 항상 "utf-8-sig" 로 읽고 "utf-8-sig" 를 돌려준다(BOM 이 있어도 첫 열 이름이 깨지지 않게)
    - mapping 에서 파일에 없는 키는 무시하고, mapping 에 없는 열은 파일의 열 이름 그대로 둔다
    - 줄 번호는 그 행이 시작하는 실제 줄 번호(머리글이 1번 줄). 빈 줄은 건너뛴다
    - 값은 바꾸지 않은 문자열 그대로. 머리글 이름만 양끝 공백을 지운다
    - 열 수가 맞지 않는 행도 돌려준다(csv.DictReader 방식): 모자란 열은 None, 남는 값은 키 None 에 list
    - 빈 파일·머리글만 있는 파일은 (인코딩, [])
    - 빈 머리글 이름, 머리글 이름 중복, 두 열이 같은 필드 이름, 받지 않는 encoding, dict 가 아닌 mapping,
      그 인코딩으로 풀 수 없음은 ValueError. 파일이 없거나 읽을 수 없으면 OSError 그대로
    """
    if mapping is not None and not isinstance(mapping, dict):
        raise ValueError(f"mapping 은 dict 나 None 이어야 합니다: {mapping!r}")
    if encoding is None:
        encoding = detect_encoding(path)
    if encoding not in ("utf-8", "utf-8-sig", "cp949"):
        raise ValueError(f"받지 않는 인코딩입니다(utf-8, utf-8-sig, cp949만): {encoding!r}")
    if encoding == "utf-8":
        encoding = "utf-8-sig"

    lines = []  # (그 행이 시작하는 줄 번호, 행)
    try:
        with open(path, encoding=encoding, newline="") as f:
            reader = csv.reader(f)
            while True:
                start = reader.line_num + 1
                try:
                    row = next(reader)
                except StopIteration:
                    break
                lines.append((start, row))
    except UnicodeDecodeError:
        raise ValueError(f"{encoding}로 읽을 수 없습니다: {path}") from None
    if not lines:
        return encoding, []

    header = [name.strip() for name in lines[0][1]]
    if not header or "" in header:
        raise ValueError(f"머리글(1번 줄)에 빈 열 이름이 있습니다: {lines[0][1]!r}")
    repeated = sorted({name for name in header if header.count(name) > 1})
    if repeated:
        raise ValueError(f"머리글의 열 이름이 겹칩니다: {', '.join(repeated)}")
    mapping = mapping or {}
    fields = [mapping.get(name, name) for name in header]
    column_of = {}
    for name, field in zip(header, fields):
        if field in column_of:
            raise ValueError(f"두 열이 같은 필드 이름이 됩니다: {column_of[field]}, {name} → {field}")
        column_of[field] = name

    rows = []
    for start, row in lines[1:]:
        if not row:
            continue
        record = dict(zip(fields, row))
        for field in fields[len(row):]:
            record[field] = None
        if len(row) > len(fields):
            record[None] = row[len(fields):]
        rows.append((start, record))
    return encoding, rows
