"""팀 공동 작업 "자료 파일 손상 대응": Store.save(A4) 안전 저장과 Store.backups(13) 백업 목록."""

import json
import os
import re
import unittest
from unittest import mock

from helpers import NAMES, StoreCase

from moim.common.store import Store

BAK = re.compile(r"^data\.json\.\d{8}_\d{6}_\d{6}\.[0-9a-f]{8}\.bak$")


class StoreSaveTest(StoreCase):
    def read(self, path=None):
        with open(path or self.store.path, encoding="utf-8") as f:
            return json.load(f)

    def test_first_save_writes_file_without_backup(self):
        self.store.save()
        self.assertEqual(self.read()["members"][0]["name"], NAMES[0])
        self.assertEqual(self.store.backups(), [])

    def test_second_save_backs_up_previous_content(self):
        self.store.save()
        self.store.data["next_id"] = 7
        self.store.save()
        (bak,) = self.store.backups()
        self.assertRegex(os.path.basename(bak), BAK)
        self.assertEqual(os.path.dirname(bak), os.path.abspath(self.path("backup")))
        self.assertEqual(self.read(bak)["next_id"], 1)       # 백업은 바꾸기 전 내용
        self.assertEqual(self.read()["next_id"], 7)          # 주 파일은 새 내용

    def test_keeps_only_newest_backups(self):
        store = Store(self.store.path, self.path("backup"), keep=3)
        for n in range(1, 7):
            store.data["next_id"] = n
            store.save()
        kept = store.backups()
        self.assertEqual(len(kept), 3)
        self.assertEqual([self.read(b)["next_id"] for b in kept], [3, 4, 5])   # 가장 오래된 1·2 삭제
        self.assertEqual(self.read()["next_id"], 6)

    def test_crash_while_writing_keeps_old_file(self):
        self.store.save()
        self.store.data["next_id"] = 99
        with mock.patch("moim.common.store.json.dump", side_effect=OSError("디스크 오류")):
            with self.assertRaises(OSError):
                self.store.save()
        self.assertEqual(self.read()["next_id"], 1)          # 주 파일은 깨지지 않고 예전 그대로
        self.assertEqual([n for n in os.listdir(self.dir) if n.endswith(".tmp")], [])   # 임시 파일 정리

    def test_keeps_every_key(self):
        self.store.data["locks"].append({"start": "2026-11-01", "end": "2026-11-30"})
        self.store.data["unknown_key"] = {"memo": "모르는 키도 그대로"}
        self.store.save()
        loaded = Store(self.store.path, self.path("backup")).load()
        self.assertEqual(loaded.data, self.store.data)

    def test_korean_is_saved_as_is(self):
        self.store.save()
        with open(self.store.path, encoding="utf-8") as f:
            self.assertIn(NAMES[0], f.read())                # ensure_ascii=False


class StoreBackupsTest(StoreCase):
    def make(self, name, mtime):
        os.makedirs(self.path("backup"), exist_ok=True)
        full = os.path.join(self.path("backup"), name)
        with open(full, "w", encoding="utf-8") as f:
            f.write("{}")
        os.utime(full, (mtime, mtime))
        return os.path.abspath(full)

    def test_no_folder_or_no_backup(self):
        self.assertEqual(self.store.backups(), [])
        os.makedirs(self.path("backup"))
        self.assertEqual(self.store.backups(), [])

    def test_oldest_first_by_mtime_then_name(self):
        b2 = self.make("data.json.20261118_090000_000001.5e6f7a8b.bak", 2000)
        b1 = self.make("data.json.20261117_090000_000001.1a2b3c4d.bak", 1000)
        b3 = self.make("data.json.20261118_090000_000002.00000000.bak", 2000)
        self.assertEqual(self.store.backups(), [b1, b2, b3])

    def test_only_this_data_files_backups(self):
        keep = self.make("data.json.20261117_090000_000001.1a2b3c4d.bak", 1000)
        self.make("other.json.20261117_090000_000001.1a2b3c4d.bak", 1000)   # 다른 자료 파일
        self.make("data.json.broken.20261117_090000", 1000)                 # .bak 아님
        os.makedirs(os.path.join(self.path("backup"), "data.json.dir.bak"))  # 폴더
        self.assertEqual(self.store.backups(), [keep])

    def test_broken_backup_is_listed_and_untouched(self):
        bad = self.make("data.json.20261117_090000_000001.1a2b3c4d.bak", 1000)
        with open(bad, "w", encoding="utf-8") as f:
            f.write("{깨진")
        self.assertEqual(self.store.backups(), [bad])
        with open(bad, encoding="utf-8") as f:
            self.assertEqual(f.read(), "{깨진")

    def test_bad_path_type_raises(self):
        for path, backup in ((None, "backup"), (self.store.path, 3)):
            with self.subTest(path=path, backup=backup), self.assertRaises(ValueError):
                Store(path, backup).backups()


if __name__ == "__main__":
    unittest.main()
