#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpaceAnalyzer - 磁盘空间分析器
"""

import os
import sys
import subprocess
import heapq
import time
from pathlib import Path
from typing import List, Tuple, Dict
from .index_store import IndexStore


class SpaceAnalyzer:
    """磁盘空间分析器"""
    
    def __init__(self):
        self.warning_threshold = 80  # 警告阈值百分比
        self.critical_threshold = 90  # 严重阈值百分比
        # 忽略的目录列表, 这些目录时系统目录，不需要分析
        self.ignore_dir_list = [
            "/System",  # 系统目录
            "/Volumes", # 外部挂载卷
            "/private", # 私有目录            
            ".Trash", # 垃圾桶
            ".localized", # 本地化目录
        ]

    
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

                # 过滤以ignore_dir_list中的目录开头的文件
                if any(dirpath.startswith(dir) for dir in self.ignore_dir_list):
                    continue

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
                        sys.stdout.write(f"\r\033[K-> 正在读取: \033[36m{dirpath_display}\033[0m    已扫描: \033[32m{scanned}\033[0m")
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

        
        
        directory_sizes = []
        
        try:
            # 获取根目录下的直接子目录
            for item in os.listdir(root_path):
                item_path = os.path.join(root_path, item)
                
                # 跳过隐藏文件和系统文件
                if item.startswith('.') and item not in ['.Trash', '.localized']:
                    continue

                if item_path in self.ignore_dir_list:
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
            # 计算内存使用率（基于 vm_stat 与页面大小）
            try:
                pagesize_res = subprocess.run(['sysctl', '-n', 'hw.pagesize'], capture_output=True, text=True)
                pagesize = int(pagesize_res.stdout.strip()) if pagesize_res.returncode == 0 else 4096
                vm_res = subprocess.run(['vm_stat'], capture_output=True, text=True)
                if vm_res.returncode == 0:
                    import re
                    page_counts = {}
                    for line in vm_res.stdout.splitlines():
                        if ':' not in line:
                            continue
                        key, val = line.split(':', 1)
                        m = re.search(r"(\d+)", val.replace('.', ''))
                        if not m:
                            continue
                        count = int(m.group(1))
                        page_counts[key.strip()] = count

                    free_pages = page_counts.get('Pages free', 0) + page_counts.get('Pages speculative', 0)
                    active_pages = page_counts.get('Pages active', 0)
                    inactive_pages = page_counts.get('Pages inactive', 0)
                    wired_pages = page_counts.get('Pages wired down', 0) or page_counts.get('Pages wired', 0)
                    compressed_pages = page_counts.get('Pages occupied by compressor', 0)

                    used_pages = active_pages + inactive_pages + wired_pages + compressed_pages
                    total_pages = used_pages + free_pages
                    if total_pages > 0:
                        usage_percent = (used_pages / total_pages) * 100.0
                        system_info["内存使用率"] = f"{usage_percent:.1f}%"
            except Exception:
                # 安静失败，不影响主流程
                print("计算内存使用率失败")
                pass
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
        
        # 添加 space-cli 版本信息
        try:
            # 简单解析 pyproject.toml 文件中的版本号
            with open('pyproject.toml', 'r', encoding='utf-8') as f:
                content = f.read()
                # 查找 version = "x.x.x" 行
                import re
                version_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                if version_match:
                    system_info['SpaceCli Version'] = version_match.group(1)
                else:
                    system_info['SpaceCli Version'] = '未知'
        except Exception:
            system_info['SpaceCli Version'] = '未知'
        
        return system_info
    
    def memory_cleanup(self) -> Dict:
        """执行内存释放优化"""
        cleanup_results = {
            "purged_memory": 0,
            "cleared_caches": [],
            "freed_swap": 0,
            "errors": []
        }
        
        try:
            
            # 2. 强制垃圾回收
            print("🔄 正在执行垃圾回收...")
            import gc
            collected = gc.collect()
            cleanup_results["purged_memory"] += collected
            
            # 3. 清理 Python 缓存
            print("🗑️ 正在清理 Python 缓存...")
            try:
                # 清理 __pycache__ 目录
                import shutil
                for root, dirs, files in os.walk('/tmp'):
                    for dir_name in dirs:
                        if dir_name == '__pycache__':
                            cache_path = os.path.join(root, dir_name)
                            try:
                                shutil.rmtree(cache_path)
                                cleanup_results["cleared_caches"].append(f"Python缓存: {cache_path}")
                            except Exception:
                                pass
            except Exception as e:
                cleanup_results["errors"].append(f"Python缓存清理失败: {e}")
            
            # 4. 清理临时文件
            print("📁 正在清理临时文件...")
            temp_dirs = ['/tmp', '/var/tmp']
            for temp_dir in temp_dirs:
                if os.path.exists(temp_dir):
                    try:
                        for item in os.listdir(temp_dir):
                            item_path = os.path.join(temp_dir, item)
                            # 只清理超过1小时的文件
                            if os.path.isfile(item_path):
                                file_age = time.time() - os.path.getmtime(item_path)
                                if file_age > 3600:  # 1小时
                                    try:
                                        os.remove(item_path)
                                        cleanup_results["cleared_caches"].append(f"临时文件: {item_path}")
                                    except Exception:
                                        pass
                    except Exception as e:
                        cleanup_results["errors"].append(f"临时文件清理失败: {e}")
            
            # 5. 尝试释放交换空间（需要管理员权限）
            print("💾 正在尝试释放交换空间...（需要登录密码授权此操作，此操作不会保存密码）")
            try:
                # 检查交换使用情况
                swap_result = subprocess.run(['sysctl', 'vm.swapusage'], 
                                           capture_output=True, text=True)
                if swap_result.returncode == 0:
                    # 尝试释放未使用的交换空间
                    subprocess.run(['sudo', 'purge'], capture_output=True, text=True)
                    cleanup_results["freed_swap"] = 1
            except Exception as e:
                cleanup_results["errors"].append(f"交换空间释放失败: {e}")
            
        except Exception as e:
            cleanup_results["errors"].append(f"内存清理过程出错: {e}")
        
        return cleanup_results
