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
    """CSV 를 읽어 (인코딩, [(줄 번호, {필드: 값})]) 를 돌려준다. mapping: {파일 열 이름: 필드 이름}"""
    raise NotImplementedError("기능 6 담당이 구현한다")
