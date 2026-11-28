"""팀 공동 작업 "로그": 실행한 명령과 오류를 날짜별 로그 파일(logs/YYYY-MM-DD.log)에 기록. 담당: 신동훈"""

import datetime as dt
import logging
import os
import shutil
import tempfile
import unittest

from moim.common import log


class GetLoggerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dir = os.path.join(self.tmp, "logs")

    def tearDown(self):
        log.get_logger(None)   # 다른 테스트에 영향이 없게 기록 안 하는 상태로 돌려 둔다
        shutil.rmtree(self.tmp, ignore_errors=True)

    def today_file(self):
        return os.path.join(self.dir, dt.date.today().strftime("%Y-%m-%d") + ".log")

    def read(self, path):
        with open(path, encoding="utf-8") as f:
            return f.read().splitlines()

    def test_writes_daily_file(self):
        logger = log.get_logger(self.dir)
        self.assertEqual(logger.name, "moim")
        self.assertFalse(os.path.exists(self.dir))   # 폴더는 처음 기록할 때 만든다
        logger.info("명령: cat apply --preview")
        logger.error("오류: 없는 규칙 번호입니다: 3")
        lines = self.read(self.today_file())
        self.assertEqual(len(lines), 2)
        self.assertRegex(lines[0], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} INFO 명령: cat apply --preview$")
        self.assertRegex(lines[1], r" ERROR 오류: 없는 규칙 번호입니다: 3$")

    def test_appends_and_no_duplicate_handler(self):
        log.get_logger(self.dir).info("첫 실행")
        logger = log.get_logger(self.dir)   # 다음 실행에서 다시 불러도
        logger.info("둘째 실행")
        self.assertEqual(len(logger.handlers), 1)
        self.assertEqual([line.split(" INFO ")[1] for line in self.read(self.today_file())], ["첫 실행", "둘째 실행"])

    def test_file_follows_record_date(self):
        handler = log.get_logger(self.dir).handlers[0]
        record = logging.LogRecord("moim", logging.INFO, __file__, 1, "자정 넘김", None, None)
        record.created = dt.datetime(2026, 11, 30, 23, 59, 59).timestamp()
        handler.handle(record)
        record.created = dt.datetime(2026, 12, 1, 0, 0, 1).timestamp()
        handler.handle(record)
        self.assertEqual(sorted(os.listdir(self.dir)), ["2026-11-30.log", "2026-12-01.log"])
        self.assertTrue(self.read(os.path.join(self.dir, "2026-12-01.log"))[0].startswith("2026-12-01 00:00:01 INFO"))

    def test_level_and_no_screen_output(self):
        logger = log.get_logger(self.dir)
        logger.debug("자세한 내용")   # INFO 아래는 남기지 않는다
        logger.warning("주의")
        self.assertFalse(logger.propagate)
        self.assertEqual(len(self.read(self.today_file())), 1)

    def test_no_dir_writes_nothing(self):
        for value in (None, "", "  "):
            with self.subTest(log_dir=value):
                logger = log.get_logger(value)
                logger.error("기록 안 됨")
                self.assertIsInstance(logger.handlers[0], logging.NullHandler)
        self.assertFalse(os.path.exists(self.dir))

    def test_switch_dir_and_bad_value(self):
        other = os.path.join(self.tmp, "other")
        log.get_logger(self.dir).info("앞")
        log.get_logger(other).info("뒤")   # 마지막에 준 폴더에만 남는다
        self.assertEqual(len(self.read(self.today_file())), 1)
        self.assertEqual(len(os.listdir(other)), 1)
        for bad in (3, ["logs"], True):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    log.get_logger(bad)


if __name__ == "__main__":
    unittest.main()
