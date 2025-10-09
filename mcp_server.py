#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpaceCli MCP Server

基于 Model Context Protocol (MCP) 的轻量服务，向兼容的客户端暴露以下工具：
- disk_health(path="/")
- largest_directories(path="/", top_n=20, use_index=True, reindex=False, index_ttl=24)
- app_analysis(top_n=20, use_index=True, reindex=False, index_ttl=24)
- big_files(path="/", top_n=20, min_size="0")

运行：
  python3 mcp_server.py

依赖：
  pip install mcp
"""

import os
import sys
from typing import Dict, List, Tuple

try:
    from mcp.server.fastmcp import FastMCP
except Exception as e:
    print("❌ 需要安装 mcp 包：pip install mcp", file=sys.stderr)
    raise

# 复用现有实现
from space_cli import SpaceAnalyzer, IndexStore


app = FastMCP("spacecli")

analyzer = SpaceAnalyzer()
index_store = IndexStore()  # 目录索引

# 应用分析索引 (~/.cache/spacecli/apps.json)
from pathlib import Path
home = str(Path.home())
app_cache_dir = os.path.join(home, ".cache", "spacecli")
os.makedirs(app_cache_dir, exist_ok=True)
app_index = IndexStore(index_file=os.path.join(app_cache_dir, "apps.json"))


def _parse_size(s: str) -> int:
    s = (s or '0').strip().upper()
    if s.endswith('K'):
        return int(float(s[:-1]) * 1024)
    if s.endswith('M'):
        return int(float(s[:-1]) * 1024**2)
    if s.endswith('G'):
        return int(float(s[:-1]) * 1024**3)
    if s.endswith('T'):
        return int(float(s[:-1]) * 1024**4)
    try:
        return int(float(s))
    except ValueError:
        return 0


@app.tool()
def disk_health(path: str = "/") -> Dict:
    """获取磁盘健康度信息"""
    usage_info = analyzer.get_disk_usage(path)
    status, message = analyzer.get_disk_health_status(usage_info)
    return {
        "disk_usage": usage_info,
        "health_status": {"status": status, "message": message},
    }


@app.tool()
def largest_directories(path: str = "/", top_n: int = 20,
                        use_index: bool = True, reindex: bool = False, index_ttl: int = 24) -> List[Dict]:
    """列出占用空间最大的目录"""
    entries = analyzer.analyze_largest_directories(
        path,
        top_n=top_n,
        index=index_store,
        use_index=use_index,
        reindex=reindex,
        index_ttl_hours=index_ttl,
        prompt=False,
    )
    return [
        {"path": p, "size_bytes": s, "size_formatted": analyzer.format_bytes(s)}
        for p, s in entries
    ]


@app.tool()
def app_analysis(top_n: int = 20, use_index: bool = True, reindex: bool = False, index_ttl: int = 24) -> List[Dict]:
    """应用目录占用分析（聚合）"""
    # 复用 SpaceCli.analyze_app_directories 逻辑（在此简单实现）
    from space_cli import SpaceCli
    cli = SpaceCli()
    cli.args = type("Args", (), {  # 简易参数对象
        "use_index": use_index, "reindex": reindex, "index_ttl": index_ttl, "no_prompt": True,
    })()
    apps = cli.analyze_app_directories(top_n=top_n, index=app_index, use_index=use_index,
                                       reindex=reindex, index_ttl_hours=index_ttl, prompt=False)
    return [
        {"app": name, "size_bytes": size, "size_formatted": analyzer.format_bytes(size)}
        for name, size in apps
    ]


@app.tool()
def big_files(path: str = "/", top_n: int = 20, min_size: str = "0") -> List[Dict]:
    """列出路径下最大的文件"""
    min_bytes = _parse_size(min_size)
    files = analyzer.analyze_largest_files(path, top_n=top_n, min_size_bytes=min_bytes)
    return [
        {"path": p, "size_bytes": s, "size_formatted": analyzer.format_bytes(s)}
        for p, s in files
    ]


if __name__ == "__main__":
    app.run()


