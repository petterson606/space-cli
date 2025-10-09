#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpaceCli - Mac OS 磁盘空间分析工具
用于检测磁盘空间健康度并列出占用空间最大的目录
"""

import os
import sys
import argparse
import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple, Dict
import json
import time
from datetime import datetime, timedelta
import heapq


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


class SpaceAnalyzer:
    """磁盘空间分析器"""
    
    def __init__(self):
        self.warning_threshold = 80  # 警告阈值百分比
        self.critical_threshold = 90  # 严重阈值百分比
    
    def get_disk_usage(self, path: str = "/") -> Dict:
        """获取磁盘使用情况"""
        try:
            statvfs = os.statvfs(path)
            
            # 计算磁盘空间信息
            total_bytes = statvfs.f_frsize * statvfs.f_blocks
            free_bytes = statvfs.f_frsize * statvfs.f_bavail
            used_bytes = total_bytes - free_bytes
            
            # 计算百分比
            usage_percent = (used_bytes / total_bytes) * 100
            
            return {
                'total': total_bytes,
                'used': used_bytes,
                'free': free_bytes,
                'usage_percent': usage_percent,
                'path': path
            }
        except Exception as e:
            print(f"错误：无法获取磁盘使用情况 - {e}")
            return None
    
    def get_disk_health_status(self, usage_info: Dict) -> Tuple[str, str]:
        """评估磁盘健康状态"""
        if not usage_info:
            return "未知", "无法获取磁盘信息"
        
        usage_percent = usage_info['usage_percent']
        
        if usage_percent >= self.critical_threshold:
            return "严重", "磁盘空间严重不足！请立即清理磁盘空间"
        elif usage_percent >= self.warning_threshold:
            return "警告", "磁盘空间不足，建议清理一些文件"
        else:
            return "良好", "磁盘空间充足"
    
    def format_bytes(self, bytes_value: int) -> str:
        """格式化字节数为人类可读格式"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"
    
    def get_directory_size(self, path: str) -> int:
        """高性能计算目录大小。

        优先使用 macOS 的 du -sk（以 KiB 为单位，速度快，原生命令可处理边界情况），
        若 du 调用失败则回退到基于 os.scandir 的非递归遍历实现（避免 os.walk 的函数调用开销）。
        """
        # 优先尝试 du -sk（BSD du 在 macOS 可用）。
        try:
            # du 输出形如: "<kib>\t<path>\n"
            result = subprocess.run([
                'du', '-sk', path
            ], capture_output=True, text=True, check=True)
            out = result.stdout.strip().split('\t', 1)[0].strip()
            kib = int(out)
            return kib * 1024
        except Exception:
            # du 不可用或失败时回退到 Python 实现
            pass

        total_size = 0
        # 基于栈的迭代遍历，避免递归栈与 os.walk 的额外开销
        stack = [path]
        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as it:
                    for entry in it:
                        # 跳过符号链接，避免循环与跨文件系统问题
                        try:
                            if entry.is_symlink():
                                continue
                            if entry.is_file(follow_symlinks=False):
                                try:
                                    total_size += entry.stat(follow_symlinks=False).st_size
                                except (OSError, FileNotFoundError, PermissionError):
                                    continue
                            elif entry.is_dir(follow_symlinks=False):
                                stack.append(entry.path)
                        except (OSError, FileNotFoundError, PermissionError):
                            continue
            except (OSError, FileNotFoundError, PermissionError):
                # 无法进入该目录则跳过
                continue
        return total_size

    def analyze_largest_files(self, root_path: str = "/", top_n: int = 50,
                               min_size_bytes: int = 0) -> List[Tuple[str, int]]:
        """扫描并返回体积最大的文件列表"""
        print("正在扫描大文件，这可能需要一些时间...")
        heap: List[Tuple[int, str]] = []  # 最小堆 (size, path)
        scanned = 0
        try:
            for dirpath, dirnames, filenames in os.walk(root_path):
                # 进度提示：单行覆盖当前目录
                dirpath_display = dirpath[-80:] # 截取最后50个字符
                if dirpath_display == "":
                    dirpath_display = dirpath
                sys.stdout.write(f"\r\033[K-> 正在读取: \033[36m{dirpath_display}\033[0m")
                sys.stdout.flush()
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        size = os.path.getsize(filepath)
                    except (OSError, FileNotFoundError, PermissionError):
                        continue
                    if size < min_size_bytes:
                        continue
                    if len(heap) < top_n:
                        heapq.heappush(heap, (size, filepath))
                    else:
                        if size > heap[0][0]:
                            heapq.heapreplace(heap, (size, filepath))
                    scanned += 1
                    if scanned % 500 == 0:
                        dirpath_display = dirpath[-80:] # 截取最后50个字符
                        if dirpath_display == "":
                            dirpath_display = dirpath
                        # 间隔性进度输出（单行覆盖）
                        sys.stdout.write(f"\r\033[K-> 正在读取: \033[36m{dirpath_display}\033[0m    已扫描文件数: \033[32m{scanned}\033[0m")
                        sys.stdout.flush()
        except KeyboardInterrupt:
            print("\n用户中断扫描，返回当前结果...")
        except Exception as e:
            print(f"扫描时出错: {e}")
        finally:
            sys.stdout.write("\n")
            sys.stdout.flush()
        # 转换为按体积降序列表
        result = sorted([(p, s) for s, p in heap], key=lambda x: x[1], reverse=False)
        result.sort(key=lambda x: x[1])
        result = sorted([(p, s) for s, p in heap], key=lambda x: x[1])
        # 正确：按 size 降序
        result = sorted([(p, s) for s, p in heap], key=lambda x: x[1], reverse=True)
        # 以上为了避免编辑器误合并，最终以最后一行排序为准
        return result
    
    def analyze_largest_directories(self, root_path: str = "/", max_depth: int = 2, top_n: int = 20,
                                    index: IndexStore = None, use_index: bool = True,
                                    reindex: bool = False, index_ttl_hours: int = 24,
                                    prompt: bool = True) -> List[Tuple[str, int]]:
        """分析占用空间最大的目录（支持索引缓存）"""
        # 索引命中
        if use_index and index and not reindex and index.is_fresh(root_path, index_ttl_hours):
            cached = index.get(root_path)
            if cached and cached.get("entries"):
                if prompt and sys.stdin.isatty():
                    try:
                        ans = input("检测到最近索引，是否使用缓存结果而不重新索引？[Y/n]: ").strip().lower()
                        if ans in ("", "y", "yes"):
                            return [(e["path"], int(e["size"])) for e in cached["entries"]][:top_n]
                    except EOFError:
                        pass
                else:
                    return [(e["path"], int(e["size"])) for e in cached["entries"]][:top_n]

        print("正在分析目录大小，这可能需要一些时间...")

        # 忽略的目录列表, 这些目录时系统目录，不需要分析
        ignore_dir_list = [
            "/System",  # 系统目录
            "/Volumes", # 外部挂载卷
            "/private", # 私有目录
        ]

        
        directory_sizes = []
        
        try:
            # 获取根目录下的直接子目录
            for item in os.listdir(root_path):
                item_path = os.path.join(root_path, item)
                
                # 跳过隐藏文件和系统文件
                if item.startswith('.') and item not in ['.Trash', '.localized']:
                    continue

                if item_path in ignore_dir_list:
                    continue
                
                if os.path.isdir(item_path):
                    try:
                        # 进度提示：当前正在读取的目录（单行覆盖）
                        sys.stdout.write(f"\r\033[K-> 正在读取: \033[36m{item_path}\033[0m")
                        sys.stdout.flush()
                        size = self.get_directory_size(item_path)
                        directory_sizes.append((item_path, size))
                        #print(f"已分析: {item_path} ({self.format_bytes(size)})")
                        print(f" ({self.format_bytes(size)})\033[0m")
                    except (OSError, PermissionError):
                        print(f"跳过无法访问的目录: {item_path}")
                        continue
            # 结束时换行，避免后续输出粘连在同一行
            sys.stdout.write("\n")
            sys.stdout.flush()
            
            # 按大小排序
            directory_sizes.sort(key=lambda x: x[1], reverse=True)
            # 写入索引
            if index:
                try:
                    index.set(root_path, directory_sizes)
                except Exception:
                    pass
            return directory_sizes[:top_n]
            
        except Exception as e:
            print(f"分析目录时出错: {e}")
            return []
    
    def get_system_info(self) -> Dict:
        """获取系统信息（包括 CPU、内存、GPU、硬盘等硬件信息）"""
        system_info = {}
        
        try:
            # 获取系统版本信息
            result = subprocess.run(['sw_vers'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    system_info[key.strip()] = value.strip()
        except Exception:
            system_info["ProductName"] = "macOS"
            system_info["ProductVersion"] = "未知"
        
        try:
            # 获取 CPU 信息
            cpu_result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], 
                                     capture_output=True, text=True)
            if cpu_result.returncode == 0:
                system_info["CPU"] = cpu_result.stdout.strip()
            
            # 获取 CPU 核心数
            cores_result = subprocess.run(['sysctl', '-n', 'hw.ncpu'], 
                                        capture_output=True, text=True)
            if cores_result.returncode == 0:
                system_info["CPU核心数"] = cores_result.stdout.strip()
                
        except Exception:
            system_info["CPU"] = "未知"
            system_info["CPU核心数"] = "未知"
        
        try:
            # 获取内存信息
            mem_result = subprocess.run(['sysctl', '-n', 'hw.memsize'], 
                                     capture_output=True, text=True)
            if mem_result.returncode == 0:
                mem_bytes = int(mem_result.stdout.strip())
                system_info["内存"] = self.format_bytes(mem_bytes)
        except Exception:
            system_info["内存"] = "未知"
                
        
        try:
            # 获取启动时间
            boot_result = subprocess.run(['uptime'], capture_output=True, text=True)
            if boot_result.returncode == 0:
                uptime_line = boot_result.stdout.strip()
                system_info["运行时间"] = uptime_line
        except Exception:
            system_info["运行时间"] = "未知"
        
        return system_info


class SpaceCli:
    """SpaceCli 主类"""
    
    def __init__(self):
        self.analyzer = SpaceAnalyzer()
        self.index = IndexStore()
        # 应用分析缓存存放于 ~/.cache/spacecli/apps.json
        home = str(Path.home())
        app_cache_dir = os.path.join(home, ".cache", "spacecli")
        os.makedirs(app_cache_dir, exist_ok=True)
        self.app_index = IndexStore(index_file=os.path.join(app_cache_dir, "apps.json"))

    # —— 应用删除相关 ——
    def _candidate_app_paths(self, app_name: str) -> List[str]:
        """根据应用名推导可能占用空间的相关目录/文件路径列表。"""
        home = str(Path.home())
        candidates: List[str] = []
        possible_bases = [
            ("/Applications", f"{app_name}.app"),
            (os.path.join(home, "Applications"), f"{app_name}.app"),
            ("/Library/Application Support", app_name),
            (os.path.join(home, "Library", "Application Support"), app_name),
            ("/Library/Caches", app_name),
            (os.path.join(home, "Library", "Caches"), app_name),
            ("/Library/Logs", app_name),
            (os.path.join(home, "Library", "Logs"), app_name),
            (os.path.join(home, "Library", "Containers"), app_name),
        ]
        # 直接拼接命中
        for base, tail in possible_bases:
            path = os.path.join(base, tail)
            if os.path.exists(path):
                candidates.append(path)
        # 模糊扫描：包含应用名的目录
        scan_dirs = [
            "/Applications",
            os.path.join(home, "Applications"),
            "/Library/Application Support",
            os.path.join(home, "Library", "Application Support"),
            "/Library/Caches",
            os.path.join(home, "Library", "Caches"),
            "/Library/Logs",
            os.path.join(home, "Library", "Logs"),
            os.path.join(home, "Library", "Containers"),
        ]
        app_lower = app_name.lower()
        for base in scan_dirs:
            if not os.path.exists(base):
                continue
            try:
                for item in os.listdir(base):
                    item_path = os.path.join(base, item)
                    # 只收集目录或 .app 包
                    if not os.path.isdir(item_path):
                        continue
                    name_lower = item.lower()
                    if app_lower in name_lower:
                        candidates.append(item_path)
            except (PermissionError, OSError):
                continue
        # 去重并按路径长度降序（先删更深层，避免空目录残留）
        uniq: List[str] = []
        seen = set()
        for p in sorted(set(candidates), key=lambda x: len(x), reverse=True):
            if p not in seen:
                uniq.append(p)
                seen.add(p)
        return uniq

    def _delete_paths_and_sum(self, paths: List[str]) -> Tuple[int, List[Tuple[str, str]]]:
        """删除给定路径列表，返回释放的总字节数与失败列表(路径, 原因)。"""
        total_freed = 0
        failures: List[Tuple[str, str]] = []
        
        def _try_fix_permissions(path: str) -> None:
            """尝试修复权限与不可变标记以便删除。"""
            try:
                # 去除不可变标记（普通用户能去除的场景）
                subprocess.run(["chflags", "-R", "nouchg", path], capture_output=True)
            except Exception:
                pass
            try:
                os.chmod(path, 0o777)
            except Exception:
                pass

        def _onerror(func, path, exc_info):
            # 当 rmtree 无法删除时，尝试修复权限并重试一次
            _try_fix_permissions(path)
            try:
                func(path)
            except Exception:
                # 让上层捕获
                raise
        for p in paths:
            try:
                size_before = 0
                try:
                    if os.path.isdir(p):
                        size_before = self.analyzer.get_directory_size(p)
                    elif os.path.isfile(p):
                        size_before = os.path.getsize(p)
                except Exception:
                    size_before = 0
                if os.path.isdir(p) and not os.path.islink(p):
                    try:
                        shutil.rmtree(p, ignore_errors=False, onerror=_onerror)
                    except Exception:
                        # 目录删除失败，降级为逐项尝试删除（尽量清理可删部分）
                        for dirpath, dirnames, filenames in os.walk(p, topdown=False):
                            for name in filenames:
                                fpath = os.path.join(dirpath, name)
                                try:
                                    _try_fix_permissions(fpath)
                                    os.remove(fpath)
                                except Exception:
                                    continue
                            for name in dirnames:
                                dpath = os.path.join(dirpath, name)
                                try:
                                    _try_fix_permissions(dpath)
                                    os.rmdir(dpath)
                                except Exception:
                                    continue
                        # 最后尝试删除顶层目录
                        _try_fix_permissions(p)
                        os.rmdir(p)
                else:
                    os.remove(p)
                total_freed += size_before
            except Exception as e:
                failures.append((p, str(e)))
        return total_freed, failures

    def _offer_app_delete(self, apps: List[Tuple[str, int]]) -> None:
        """在已打印的应用列表后，提供按序号一键删除功能。"""
        if not sys.stdin.isatty() or getattr(self.args, 'no_prompt', False):
            return
        try:
            ans = input("是否要一键删除某个应用？输入序号或回车跳过: ").strip()
        except EOFError:
            ans = ""
        if not ans:
            return
        try:
            idx = int(ans)
        except ValueError:
            print("❌ 无效的输入（应为数字序号）")
            return
        if idx < 1 or idx > len(apps):
            print("❌ 序号超出范围")
            return
        app_name, app_size = apps[idx - 1]
        size_str = self.analyzer.format_bytes(app_size)
        try:
            confirm = input(f"确认删除应用及相关缓存: {app_name} (约 {size_str})？[y/N]: ").strip().lower()
        except EOFError:
            confirm = ""
        if confirm not in ("y", "yes"):
            print("已取消删除")
            return
        related_paths = self._candidate_app_paths(app_name)
        if not related_paths:
            print("未找到可删除的相关目录/文件")
            return
        print("将尝试删除以下路径：")
        for p in related_paths:
            print(f" - {p}")
        try:
            confirm2 = input("再次确认删除以上路径？[y/N]: ").strip().lower()
        except EOFError:
            confirm2 = ""
        if confirm2 not in ("y", "yes"):
            print("已取消删除")
            return
        freed, failures = self._delete_paths_and_sum(related_paths)
        print(f"✅ 删除完成，预计释放空间: {self.analyzer.format_bytes(freed)}")
        if failures:
            print("以下路径删除失败，可能需要手动或管理员权限：")
            for p, reason in failures:
                print(f" - {p}  ->  {reason}")
            # 常见提示：Operation not permitted（SIP/容器元数据等）
            if any("Operation not permitted" in r for _, r in failures):
                print("提示：部分系统受保护或容器元数据文件无法删除。可尝试：")
                print(" - 先退出相关应用（如 Docker）再重试")
                print(" - 给予当前终端“完全磁盘访问权限”（系统设置 → 隐私与安全性）")
                print(" - 仅删除用户目录下缓存，保留系统级容器元数据")

    # 通用渲染：目录与应用（减少重复）
    def _render_dirs(self, entries: List[Tuple[str, int]], total_bytes: int) -> None:
        for i, (dir_path, size) in enumerate(entries, 1):
            size_str = self.analyzer.format_bytes(size)
            percentage = (size / total_bytes) * 100 if total_bytes else 0
            # 1G 以上红色，否则绿色
            color = "\033[31m" if size >= 1024**3 else "\033[32m"
            print(f"{i:2d}. \033[36m{dir_path}\033[0m --    大小: {color}{size_str}\033[0m (\033[33m{percentage:.2f}%\033[0m)")

    def _render_apps(self, entries: List[Tuple[str, int]], disk_total: int) -> None:
        for i, (app, size) in enumerate(entries, 1):
            size_str = self.analyzer.format_bytes(size)
            pct = (size / disk_total) * 100 if disk_total else 0
            suggestion = "建议卸载或清理缓存" if size >= 5 * 1024**3 else "可保留，定期清理缓存"
            # 3G 以上红色，否则绿色
            color = "\033[31m" if size >= 3 * 1024**3 else "\033[32m"
            print(f"{i:2d}. \033[36m{app}\033[0m  --  占用: {color}{size_str}\033[0m ({pct:.2f}%)  — {suggestion}")

    def analyze_app_directories(self, top_n: int = 20,
                                index: IndexStore = None,
                                use_index: bool = True,
                                reindex: bool = False,
                                index_ttl_hours: int = 24,
                                prompt: bool = True) -> List[Tuple[str, int]]:
        """分析应用安装与数据目录占用，按应用归并估算大小（支持缓存）"""

        # 命中命名缓存
        cache_name = "apps_aggregate"
        if use_index and index and not reindex and index.is_fresh_named(cache_name, index_ttl_hours):
            cached = index.get_named(cache_name)
            if cached and cached.get("entries"):
                if prompt and sys.stdin.isatty():
                    try:
                        ans = input("检测到最近应用分析索引，是否使用缓存结果？[Y/n]: ").strip().lower()
                        if ans in ("", "y", "yes"):
                            return [(e["name"], int(e["size"])) for e in cached["entries"]][:top_n]
                    except EOFError:
                        pass
                else:
                    return [(e["name"], int(e["size"])) for e in cached["entries"]][:top_n]
        # 关注目录
        home = str(Path.home())
        target_dirs = [
            "/Applications",
            os.path.join(home, "Applications"),
            "/Library/Application Support",
            "/Library/Caches",
            "/Library/Logs",
            os.path.join(home, "Library", "Application Support"),
            os.path.join(home, "Library", "Caches"),
            os.path.join(home, "Library", "Logs"),
            os.path.join(home, "Library", "Containers"),
        ]

        def app_key_from_path(p: str) -> str:
            # 优先用.app 名称，其次用顶级目录名
            parts = Path(p).parts
            for i in range(len(parts)-1, -1, -1):
                if parts[i].endswith('.app'):
                    return parts[i].replace('.app', '')
            # 否则返回倒数第二级或最后一级作为应用键
            return parts[-1] if parts else p

        app_size_map: Dict[str, int] = {}
        scanned_dirs: List[str] = []

        for base in target_dirs:
            if not os.path.exists(base):
                continue
            try:
                for item in os.listdir(base):
                    item_path = os.path.join(base, item)
                    if not os.path.isdir(item_path):
                        continue
                    key = app_key_from_path(item_path)
                    # 进度提示：当前应用相关目录（单行覆盖）
                    item_path = item_path[:100]
                    sys.stdout.write(f"\r\033[K-> 正在读取: \033[36m{item_path}\033[0m")
                    sys.stdout.flush()
                    size = self.analyzer.get_directory_size(item_path)
                    scanned_dirs.append(item_path)
                    app_size_map[key] = app_size_map.get(key, 0) + size
            except (PermissionError, OSError):
                continue
        # 结束时换行
        sys.stdout.write("\n")
        sys.stdout.flush()

        # 转为排序列表
        result = sorted(app_size_map.items(), key=lambda x: x[1], reverse=True)
        # 写入命名缓存
        if index:
            try:
                index.set_named(cache_name, result)
            except Exception:
                pass
        return result[:top_n]
    
    def print_disk_health(self, path: str = "/"):
        """打印磁盘健康状态"""
        print("=" * 60)
        print("🔍 磁盘空间健康度分析")
        print("=" * 60)
        
        usage_info = self.analyzer.get_disk_usage(path)
        if not usage_info:
            print("❌ 无法获取磁盘使用情况")
            return
        
        status, message = self.analyzer.get_disk_health_status(usage_info)
        
        # 状态图标
        status_icon = {
            "良好": "✅",
            "警告": "⚠️",
            "严重": "🚨"
        }.get(status, "❓")
        
        print(f"磁盘路径: \033[36m{usage_info['path']}\033[0m")
        print(f"总容量: \033[36m{self.analyzer.format_bytes(usage_info['total'])}\033[0m")
        print(f"已使用: \033[36m{self.analyzer.format_bytes(usage_info['used'])}\033[0m")
        print(f"可用空间: \033[36m{self.analyzer.format_bytes(usage_info['free'])}\033[0m")
        print(f"使用率: \033[36m{usage_info['usage_percent']:.1f}%\033[0m")
        print(f"健康状态: {status_icon} \033[36m{status}\033[0m")
        print(f"建议: \033[36m{message}\033[0m")
        print()
    
    def print_largest_directories(self, path: str = "/Library", top_n: int = 20):
        """打印占用空间最大的目录"""
        print("=" * 60)
        print("📊 占用空间最大的目录")
        print("=" * 60)
        
        # 若有缓存：直接显示缓存，然后再询问是否重新分析
        if self.args.use_index:
            cached = self.index.get(path)
            if cached and cached.get("entries"):
                cached_entries = [(e["path"], int(e["size"])) for e in cached["entries"]][:top_n]
                total_info = self.analyzer.get_disk_usage(path)
                total_bytes = total_info['total'] if total_info else 1
                print(f"(来自索引) 显示前 {min(len(cached_entries), top_n)} 个最大的目录:\n")
                self._render_dirs(cached_entries, total_bytes)
                if sys.stdin.isatty() and not self.args.no_prompt:
                    try:
                        ans = input("是否重新分析以刷新索引？[y/N]: ").strip().lower()
                    except EOFError:
                        ans = ""
                    if ans not in ("y", "yes"):
                        # 提供下探分析选项
                        self._offer_drill_down_analysis(cached_entries, path)
                        return
                else:
                    return

        directories = self.analyzer.analyze_largest_directories(
            path,
            top_n=top_n,
            index=self.index,
            use_index=self.args.use_index,
            reindex=True,  # 走到这里表示要刷新
            index_ttl_hours=self.args.index_ttl,
            prompt=False,
        )
        if not directories:
            print("❌ 无法分析目录大小")
            return
        total_info = self.analyzer.get_disk_usage(path)
        total_bytes = total_info['total'] if total_info else 1
        print("\n已重新分析，最新结果：\n")
        self._render_dirs(directories, total_bytes)
        
        # 提供下探分析选项
        self._offer_drill_down_analysis(directories, path)

    def _offer_drill_down_analysis(self, directories: List[Tuple[str, int]], current_path: str) -> None:
        """提供交互式下探分析选项"""
        if not sys.stdin.isatty() or getattr(self.args, 'no_prompt', False):
            return
        
        print("\n" + "=" * 60)
        print("🔍 下探分析选项")
        print("=" * 60)
        print("选择序号进行深度分析，选择0返回上一级，直接回车退出:")
        
        try:
            choice = input("请输入选择 [回车=退出]: ").strip()
        except EOFError:
            return
        
        if not choice:
            return
        
        try:
            idx = int(choice)
        except ValueError:
            print("❌ 无效的输入（应为数字序号）")
            return
        
        if idx == 0:
            # 返回上一级
            parent_path = os.path.dirname(current_path.rstrip('/'))
            if parent_path != current_path and parent_path != '/':
                print(f"\n🔄 返回上一级: {parent_path}")
                self.print_largest_directories(parent_path, self.args.top_n)
            else:
                print("❌ 已在根目录，无法返回上一级")
            return
        
        if idx < 1 or idx > len(directories):
            print("❌ 序号超出范围")
            return
        
        selected_path, selected_size = directories[idx - 1]
        size_str = self.analyzer.format_bytes(selected_size)
        
        print(f"\n🔍 正在分析: {selected_path} ({size_str})")
        print("=" * 60)
        
        # 递归调用下探分析
        self.print_largest_directories(selected_path, self.args.top_n)

    def print_app_analysis(self, top_n: int = 20):
        """打印应用目录占用分析，并给出卸载建议"""
        print("=" * 60)
        print("🧩 应用目录空间分析与卸载建议")
        print("=" * 60)

        # 先显示缓存，再决定是否刷新
        if self.args.use_index:
            cached = self.app_index.get_named("apps_aggregate")
            if cached and cached.get("entries"):
                cached_entries = [(e["name"], int(e["size"])) for e in cached["entries"]][:top_n]
                total = self.analyzer.get_disk_usage("/")
                disk_total = total['total'] if total else 1
                print(f"(来自索引) 显示前 {min(len(cached_entries), top_n)} 个空间占用最高的应用:\n")
                self._render_apps(cached_entries, disk_total)
                # 提供一键删除
                self._offer_app_delete(cached_entries)
                if sys.stdin.isatty() and not self.args.no_prompt:
                    try:
                        ans = input("是否重新分析应用以刷新索引？[y/N]: ").strip().lower()
                    except EOFError:
                        ans = ""
                    if ans not in ("y", "yes"):
                        return
                else:
                    return

        apps = self.analyze_app_directories(
            top_n=top_n,
            index=self.app_index,
            use_index=self.args.use_index,
            reindex=True,
            index_ttl_hours=self.args.index_ttl,
            prompt=False,
        )
        if not apps:
            print("❌ 未发现可分析的应用目录")
            return
        total = self.analyzer.get_disk_usage("/")
        disk_total = total['total'] if total else 1
        print("\n已重新分析，最新应用占用结果：\n")
        self._render_apps(apps, disk_total)
        # 提供一键删除
        self._offer_app_delete(apps)

    def print_home_deep_analysis(self, top_n: int = 20):
        """对用户目录的 Library / Downloads / Documents 分别下探分析"""
        home = str(Path.home())
        targets = [
            ("Library", os.path.join(home, "Library")),
            ("Downloads", os.path.join(home, "Downloads")),
            ("Documents", os.path.join(home, "Documents")),
        ]

        for label, target in targets:
            if not os.path.exists(target):
                continue
            print("=" * 60)
            print(f"🏠 用户目录下探 - {label}")
            print("=" * 60)
            directories = self.analyzer.analyze_largest_directories(
                target,
                top_n=top_n,
                index=self.index,
                use_index=self.args.use_index,
                reindex=self.args.reindex,
                index_ttl_hours=self.args.index_ttl,
                prompt=not self.args.no_prompt,
            )
            if not directories:
                print("❌ 无法分析目录大小")
                continue
            total_info = self.analyzer.get_disk_usage("/")
            total_bytes = total_info['total'] if total_info else 1
            print(f"显示前 {min(len(directories), top_n)} 个最大的目录:\n")
            for i, (dir_path, size) in enumerate(directories, 1):
                size_str = self.analyzer.format_bytes(size)
                percentage = (size / total_bytes) * 100
                color = "\033[31m" if size >= 1024**3 else "\033[32m"
                print(f"{i:2d}. \033[36m{dir_path}\033[0m --    大小: {color}{size_str}\033[0m (\033[33m{percentage:.2f}%\033[0m)")
                #print()

    def print_big_files(self, path: str, top_n: int = 50, min_size_bytes: int = 0):
        """打印大文件列表"""
        print("=" * 60)
        print("🗄️ 大文件分析")
        print("=" * 60)
        files = self.analyzer.analyze_largest_files(path, top_n=top_n, min_size_bytes=min_size_bytes)
        if not files:
            print("❌ 未找到符合条件的大文件")
            return
        total = self.analyzer.get_disk_usage("/")
        disk_total = total['total'] if total else 1
        for i, (file_path, size) in enumerate(files, 1):
            size_str = self.analyzer.format_bytes(size)
            pct = (size / disk_total) * 100
            color = "\033[31m" if size >= 5 * 1024**3 else ("\033[33m" if size >= 1024**3 else "\033[32m")
            print(f"{i:2d}. \033[36m{file_path}\033[0m  --  大小: {color}{size_str}\033[0m (\033[33m{pct:.2f}%\033[0m)")
        print()
    
    def print_system_info(self):
        """打印系统信息"""
        print("=" * 60)
        print("💻 系统信息")
        print("=" * 60)
        
        system_info = self.analyzer.get_system_info()
        
        for key, value in system_info.items():
            print(f"{key}: \033[36m{value}\033[0m")
        print()
    
    def export_report(self, output_file: str, path: str = "/"):
        """导出分析报告到JSON文件"""
        print(f"正在生成报告并保存到: {output_file}")
        
        usage_info = self.analyzer.get_disk_usage(path)
        status, message = self.analyzer.get_disk_health_status(usage_info)
        directories = self.analyzer.analyze_largest_directories(path)
        system_info = self.analyzer.get_system_info()
        # 可选：大文件分析
        largest_files = []
        try:
            if getattr(self, 'args', None) and getattr(self.args, 'big_files', False):
                files = self.analyzer.analyze_largest_files(
                    path,
                    top_n=getattr(self.args, 'big_files_top', 20),
                    min_size_bytes=getattr(self.args, 'big_files_min_bytes', 0),
                )
                largest_files = [
                    {
                        "path": file_path,
                        "size_bytes": size,
                        "size_formatted": self.analyzer.format_bytes(size),
                    }
                    for file_path, size in files
                ]
        except Exception:
            largest_files = []
        
        report = {
            "timestamp": subprocess.run(['date'], capture_output=True, text=True).stdout.strip(),
            "system_info": system_info,
            "disk_usage": usage_info,
            "health_status": {
                "status": status,
                "message": message
            },
            "largest_directories": [
                {
                    "path": dir_path,
                    "size_bytes": size,
                    "size_formatted": self.analyzer.format_bytes(size)
                }
                for dir_path, size in directories
            ],
            "largest_files": largest_files
        }
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"✅ 报告已保存到: {output_file}")
        except Exception as e:
            print(f"❌ 保存报告失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="SpaceCli - Mac OS 磁盘空间分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python space_cli.py                    # 分析根目录
  python space_cli.py -p /Users          # 分析用户目录
  python space_cli.py -n 10              # 显示前10个最大目录
  python space_cli.py --export report.json  # 导出报告
  python space_cli.py --health-only      # 只显示健康状态
        """
    )
    
    parser.add_argument(
        '-p', '--path',
        default='/',
        help='要分析的路径 (默认: /)'
    )

    # 快捷：分析当前用户目录
    parser.add_argument(
        '--home',
        action='store_true',
        help='将分析路径设置为当前用户目录（$HOME）'
    )
    
    parser.add_argument(
        '-n', '--top-n',
        type=int,
        default=20,
        help='显示前N个最大的目录 (默认: 20)'
    )
    
    parser.add_argument(
        '--health-only',
        action='store_true',
        help='只显示磁盘健康状态'
    )
    
    parser.add_argument(
        '--directories-only',
        action='store_true',
        help='只显示目录分析'
    )

    # 索引相关
    parser.add_argument(
        '--use-index',
        dest='use_index',
        action='store_true',
        help='使用已存在的索引缓存（若存在）'
    )
    parser.add_argument(
        '--no-index',
        dest='use_index',
        action='store_false',
        help='不使用索引缓存'
    )
    parser.set_defaults(use_index=True)
    parser.add_argument(
        '--reindex',
        action='store_true',
        help='强制重建索引'
    )
    parser.add_argument(
        '--index-ttl',
        type=int,
        default=24,
        help='索引缓存有效期（小时），默认24小时'
    )
    parser.add_argument(
        '--no-prompt',
        action='store_true',
        help='非交互模式：不提示是否使用缓存'
    )

    # 应用分析
    parser.add_argument(
        '--apps',
        action='store_true',
        help='显示应用目录空间分析与卸载建议'
    )

    # 大文件分析
    parser.add_argument(
        '--big-files',
        action='store_true',
        help='显示大文件分析结果'
    )
    parser.add_argument(
        '--big-files-top',
        type=int,
        default=20,
        help='大文件分析显示前N个（默认20）'
    )
    parser.add_argument(
        '--big-files-min',
        type=str,
        default='0',
        help='只显示大于该阈值的文件，支持K/M/G/T，如 500M、2G，默认0'
    )
    
    parser.add_argument(
        '--export',
        metavar='FILE',
        help='导出分析报告到JSON文件'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='SpaceCli 1.0.0'
    )
    
    args = parser.parse_args()

    # 解析 --big-files-min 阈值字符串到字节
    def parse_size(s: str) -> int:
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
    args.big_files_min_bytes = parse_size(getattr(args, 'big_files_min', '0'))
    
    # 交互式菜单：当未传入任何参数时触发（默认执行全部分析）
    if len(sys.argv) == 1:
        print("=" * 60)
        print("🧭 SpaceCli 菜单（直接回车 = 执行全部项目）")
        print("=" * 60)
        home_path = str(Path.home())
        print("1) \033[36m执行主要项目（系统信息 + 健康 +  应用）\033[0m")
        print(f"2) \033[36m当前用户目录分析（路径: {home_path}）\033[0m")
        print("3) \033[36m仅显示系统信息\033[0m")
        print("4) \033[36m仅显示磁盘健康状态\033[0m")
        print("5) \033[36m交互式目录空间分析\033[0m")
        print("6) \033[36m仅分析程序应用目录空间\033[0m")
        print("7) \033[36m仅进行大文件分析（很耗时，可随时终止）\033[0m")
        print("0) \033[36m退出\033[0m")
        try:
            choice = input("请选择 [回车=1]: ").strip()
        except EOFError:
            choice = ""

        if choice == "0": # 退出
            sys.exit(0)
        elif choice == "2": # 仅显示当前用户目录分析
            args.path = home_path
            args.apps = False
            args.health_only = False
            args.directories_only = False
        elif choice == "3": # 仅显示系统信息
            args.health_only = False
            args.directories_only = False
            args.apps = False
            args.big_files = False
        elif choice == "4": # 仅显示磁盘健康状态 
            args.health_only = True
            args.directories_only = False
            args.apps = False
            args.big_files = False
        elif choice == "5": # 仅显示最大目录列表
            args.health_only = False
            args.directories_only = True
            args.apps = False
            args.big_files = False
        elif choice == "6": # 仅显示应用目录分析与建议
            args.health_only = False
            args.directories_only = False
            args.apps = True
            args.big_files = False
        elif choice == "7": # 仅显示大文件分析
            args.health_only = False
            args.directories_only = False
            args.apps = False
            args.big_files = True
        else: # 默认执行全部（用户不选择，或者选择1）            
            args.health_only = True
            args.directories_only = False
            args.big_files = False
            args.apps = True            


    # --home 优先设置路径
    if getattr(args, 'home', False):
        args.path = str(Path.home())

    # 检查路径是否存在
    if not os.path.exists(args.path):
        print(f"❌ 错误: 路径 '{args.path}' 不存在")
        sys.exit(1)
    
    # 创建SpaceCli实例
    space_cli = SpaceCli()
    # 让 SpaceCli 实例可访问参数（用于索引与提示控制）
    space_cli.args = args
    
    try:
        # 显示系统信息
        space_cli.print_system_info()
        
        # 显示磁盘健康状态
        if args.health_only:
            space_cli.print_disk_health(args.path)
        
        # 显示目录分析
        if args.directories_only or args.path !='/':
            space_cli.print_largest_directories(args.path, args.top_n)
            # 若分析路径为当前用户目录，做深度分析
            if os.path.abspath(args.path) == os.path.abspath(str(Path.home())):
                space_cli.print_home_deep_analysis(args.top_n)

        # 应用目录分析
        if args.apps:
            space_cli.print_app_analysis(args.top_n)

        # 大文件分析
        #if getattr(args, 'big_files', False):
        if args.big_files:
            space_cli.print_big_files(args.path, top_n=args.big_files_top, min_size_bytes=args.big_files_min_bytes)
        
        # 导出报告
        if args.export:
            space_cli.export_report(args.export, args.path)
        
        print("=" * 60)
        print("✅ 分析完成！")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n❌ 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
