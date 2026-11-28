"""로그. 팀 공동 작업 "로그" 담당이 날짜별 파일(logs/YYYY-MM-DD.log)에 남기도록 완성한다. 담당: 로그(신동훈)

쓰는 곳: 통합 실행(moim/cli.py)이 실행한 명령과 오류를 남길 때.
    logger = get_logger(cfg.get("log_dir", "logs"))
    logger.info("명령: %s", " ".join(argv))
    logger.error("오류: %s", exc)
"""

import datetime as dt
import logging
import os

FORMAT = "%(asctime)s %(levelname)s %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"


class DailyFileHandler(logging.Handler):
    """기록마다 그 기록 시각의 날짜 파일(log_dir/YYYY-MM-DD.log, UTF-8)에 한 줄씩 덧붙인다.

    파일을 열어 두지 않고 기록할 때마다 열고 닫는다. 그래서 날짜가 바뀌면 다음 기록부터 새 파일에 쓰고,
    폴더는 처음 기록할 때 만든다. 로그를 쓰다 실패해도 명령 실행은 멈추지 않는다(logging 기본 동작).
    """

    def __init__(self, log_dir):
        super().__init__()
        self.log_dir = os.fspath(log_dir)
        self.setFormatter(logging.Formatter(FORMAT, DATEFMT))

    def path_for(self, record):
        day = dt.datetime.fromtimestamp(record.created).strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"{day}.log")

    def emit(self, record):
        try:
            line = self.format(record)
            os.makedirs(self.log_dir, exist_ok=True)
            with open(self.path_for(record), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            self.handleError(record)


def get_logger(log_dir):
    """'moim' 로거. log_dir 가 있으면 log_dir/YYYY-MM-DD.log 에 INFO 이상을 남긴다.

    - 여러 번 불러도 날짜 파일 처리기는 하나만 둔다(같은 줄이 두 번 남지 않는다). 마지막에 준 log_dir 를 쓴다
    - log_dir 가 None 이나 빈 문자열이면 아무 데도 기록하지 않는다
    - log_dir 가 문자열·경로가 아니면 ValueError
    - 화면(표준 오류)으로는 내보내지 않는다(propagate=False). 화면 안내는 통합 실행이 맡는다
    """
    if log_dir is not None and not isinstance(log_dir, (str, os.PathLike)):
        raise ValueError(f"로그 폴더는 경로 문자열이어야 합니다: {log_dir!r}")
    logger = logging.getLogger("moim")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    if log_dir is None or not os.fspath(log_dir).strip():
        logger.addHandler(logging.NullHandler())
    else:
        logger.addHandler(DailyFileHandler(log_dir))
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
