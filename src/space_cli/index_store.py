#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IndexStore - 目录大小索引缓存管理器
"""

import os
import json
from pathlib import Path
from typing import List, Tuple, Dict
from datetime import datetime, timedelta


class IndexStore:
    """简单的目录大小索引缓存管理器"""

    def __init__(self, index_file: str = None):
        home = str(Path.home())
        cache_dir = os.path.join(home, ".spacecli")
        os.makedirs(cache_dir, exist_ok=True)
        self.index_file = index_file or os.path.join(cache_dir, "index.json")
        self._data: Dict = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}
        self._loaded = True

    def save(self) -> None:
        try:
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _key(self, root_path: str) -> str:
        return os.path.abspath(root_path)

    def get(self, root_path: str) -> Dict:
        self.load()
        return self._data.get(self._key(root_path))

    def set(self, root_path: str, entries: List[Tuple[str, int]]) -> None:
        self.load()
        now_iso = datetime.utcnow().isoformat()
        self._data[self._key(root_path)] = {
            "updated_at": now_iso,
            "entries": [{"path": p, "size": s} for p, s in entries],
        }
        self.save()

    def is_fresh(self, root_path: str, ttl_hours: int) -> bool:
        self.load()
        rec = self._data.get(self._key(root_path))
        if not rec:
            return False
        try:
            updated_at = datetime.fromisoformat(rec.get("updated_at"))
            return datetime.utcnow() - updated_at <= timedelta(hours=ttl_hours)
        except Exception:
            return False

    # 命名缓存（非路径键），适合应用分析等聚合结果
    def get_named(self, name: str) -> Dict:
        self.load()
        return self._data.get(name)

    def set_named(self, name: str, entries: List[Tuple[str, int]]) -> None:
        self.load()
        now_iso = datetime.utcnow().isoformat()
        self._data[name] = {
            "updated_at": now_iso,
            "entries": [{"name": p, "size": s} for p, s in entries],
        }
        self.save()

    def is_fresh_named(self, name: str, ttl_hours: int) -> bool:
        self.load()
        rec = self._data.get(name)
        if not rec:
            return False
        try:
            updated_at = datetime.fromisoformat(rec.get("updated_at"))
            return datetime.utcnow() - updated_at <= timedelta(hours=ttl_hours)
        except Exception:
            return False
