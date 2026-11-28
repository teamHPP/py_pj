"""자료 파일 저장. 모든 기능이 이 한 곳의 자료(store.data)를 읽고 쓴다.

자료 구조(EMPTY)는 최소 항목만 들어 있다. 기능에 필요한 항목은 그 기능 담당자가 EMPTY 에 추가한다.
옛 자료 파일에 새 항목이 없으면 읽을 때 기본값으로 채운다.
save·backups·recover 는 팀 공동 작업 "자료 파일 손상 대응" 담당이 완성한다.
"""

import copy
import datetime as dt
import json
import os
import secrets
import shutil
import tempfile

EMPTY = {
    "members": [],      # {"name", "joined", "left"}
    "expenses": [],     # {"id", "date", "payer", "amount", "members", "category", "memo"}
    "next_id": 1,
    "history": [],      # {"at", "action", "id", "before", "after"} — 기능 1 담당(수정·삭제 이력)
    "locks": [],        # {"start", "end"} — 기능 4 담당(정산 확정 기간, 양끝 포함)
    "payments": [],     # {"id", "date", "member", "amount", "memo", "source"} — 기능 5 담당(회비 입금)
    "transfers": [],    # {"date", "from", "to", "amount"} — 기능 4 담당(이미 보낸 송금, 부분 정산)
    "recurring": [],    # {"id", "day", "payer", "amount", "members", "memo", "weights", "start_month", "last_month"} — 기능 4 담당(반복 지출)
}


class Store:
    def __init__(self, path, backup_dir=None, keep=10):
        self.path = path
        self.backup_dir = backup_dir or os.path.join(os.path.dirname(os.path.abspath(path)), "backup")
        self.keep = keep
        self.data = copy.deepcopy(EMPTY)
        self.recovered_from = None

    def load(self):
        if not os.path.exists(self.path):
            self.data = copy.deepcopy(EMPTY)
            return self
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        self._check_shape(data)
        self.data = data
        return self

    @staticmethod
    def _check_shape(data):
        """members·expenses 는 꼭 있어야 한다. 나중에 추가된 항목이 없는 옛 파일은 기본값으로 채운다."""
        if not isinstance(data, dict):
            raise ValueError("자료 파일 형식이 아닙니다")
        for key in ("members", "expenses"):
            if not isinstance(data.get(key), list):
                raise ValueError(f"자료 파일에 {key} 항목이 없습니다")
        for key, value in EMPTY.items():
            data.setdefault(key, copy.deepcopy(value))

    def save(self):
        """안전 저장(A4). 담당: 이은경(자료 파일 손상 대응)

        1. 주 자료 파일이 있으면 backup_dir 에 <자료파일명>.<YYYYMMDD_HHMMSS_ffffff>.<8자리 16진수>.bak 로 복사한다.
        2. 같은 폴더의 임시 파일에 JSON 을 쓰고, 닫은 뒤 os.replace 로 주 파일과 바꾼다.
           저장 도중 멈춰도 주 파일은 바꾸기 전 내용 그대로다.
        3. 백업이 keep 개를 넘으면 가장 오래된 것부터 지운다.
        self.data 의 모든 키(모르는 키 포함)를 그대로 쓴다. 실패하면 예외를 그대로 올린다.
        """
        path = self._checked_path()
        if os.path.exists(path):
            os.makedirs(self.backup_dir, exist_ok=True)
            stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            name = f"{os.path.basename(path)}.{stamp}.{secrets.token_hex(4)}.bak"
            shutil.copyfile(path, os.path.join(self.backup_dir, name))
        folder = os.path.dirname(path)
        fd, tmp = tempfile.mkstemp(prefix=os.path.basename(path) + ".", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        old = self.backups()
        for extra in old[:max(0, len(old) - self.keep)]:
            os.remove(extra)

    def backups(self):
        """백업 파일 목록(오래된 것부터). 담당: 이은경(자료 파일 손상 대응)

        backup_dir 안에서 <자료파일명>.*.bak 모양인 일반 파일의 절대 경로를 (수정 시각, 파일 이름) 오름차순으로
        돌려준다. 폴더가 없거나 백업이 없으면 []. 깨진 백업도 넣는다(정상인지는 recover 가 본다). 파일은 바꾸지 않는다.
        """
        path = self._checked_path()
        if not isinstance(self.backup_dir, (str, os.PathLike)):
            raise ValueError(f"백업 폴더 경로가 잘못되었습니다: {self.backup_dir!r}")
        folder = os.path.abspath(self.backup_dir)
        if not os.path.isdir(folder):
            return []
        prefix = os.path.basename(path) + "."
        found = []
        for name in os.listdir(folder):
            full = os.path.join(folder, name)
            if name.startswith(prefix) and name.endswith(".bak") and os.path.isfile(full):
                found.append((os.path.getmtime(full), name, full))
        return [full for _, _, full in sorted(found)]

    def _checked_path(self):
        """자료 파일의 절대 경로. 경로가 문자열(또는 PathLike)이 아니면 ValueError."""
        if not isinstance(self.path, (str, os.PathLike)) or not os.fspath(self.path):
            raise ValueError(f"자료 파일 경로가 잘못되었습니다: {self.path!r}")
        return os.path.abspath(self.path)

    def recover(self):
        """깨진 파일을 옆에 남기고 마지막 정상 백업을 불러온다. 불러온 백업 경로를 recovered_from 에 둔다."""
        raise NotImplementedError("자료 파일 손상 대응 담당이 구현한다")

    def new_id(self):
        eid = self.data["next_id"]
        self.data["next_id"] += 1
        return eid

    def get_expense(self, eid):
        for e in self.data["expenses"]:
            if e["id"] == int(eid):
                return e
        raise ValueError(f"{eid}번 지출이 없습니다")

    def member(self, name):
        for m in self.data["members"]:
            if m["name"] == name:
                return m
        return None

    def record(self, action, eid, before, after):
        """store.data["history"] 끝에 이력 하나를 붙인다(A3). 메모리만 바꾸고 디스크엔 저장하지 않는다.
        담당: 기능 1"""
        self.data["history"].append({
            "at": dt.datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "id": eid,
            "before": copy.deepcopy(before) if before is not None else None,
            "after": copy.deepcopy(after) if after is not None else None,
        })
