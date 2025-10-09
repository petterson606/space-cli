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
        """递归计算目录大小"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except (OSError, FileNotFoundError):
                        # 跳过无法访问的文件
                        continue
        except (OSError, PermissionError):
            # 跳过无法访问的目录
            pass
        return total_size
    
    def analyze_largest_directories(self, root_path: str = "/", max_depth: int = 2, top_n: int = 20) -> List[Tuple[str, int]]:
        """分析占用空间最大的目录"""
        print("正在分析目录大小，这可能需要一些时间...")
        
        directory_sizes = []
        
        try:
            # 获取根目录下的直接子目录
            for item in os.listdir(root_path):
                item_path = os.path.join(root_path, item)
                
                # 跳过隐藏文件和系统文件
                if item.startswith('.') and item not in ['.Trash', '.localized']:
                    continue
                
                if os.path.isdir(item_path):
                    try:
                        size = self.get_directory_size(item_path)
                        directory_sizes.append((item_path, size))
                        print(f"已分析: {item_path} ({self.format_bytes(size)})")
                    except (OSError, PermissionError):
                        print(f"跳过无法访问的目录: {item_path}")
                        continue
            
            # 按大小排序
            directory_sizes.sort(key=lambda x: x[1], reverse=True)
            return directory_sizes[:top_n]
            
        except Exception as e:
            print(f"分析目录时出错: {e}")
            return []
    
    def get_system_info(self) -> Dict:
        """获取系统信息"""
        try:
            # 获取系统版本
            result = subprocess.run(['sw_vers'], capture_output=True, text=True)
            system_info = {}
            for line in result.stdout.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    system_info[key.strip()] = value.strip()
            
            return system_info
        except Exception:
            return {"ProductName": "macOS", "ProductVersion": "未知"}


class SpaceCli:
    """SpaceCli 主类"""
    
    def __init__(self):
        self.analyzer = SpaceAnalyzer()
    
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
        
        print(f"磁盘路径: {usage_info['path']}")
        print(f"总容量: {self.analyzer.format_bytes(usage_info['total'])}")
        print(f"已使用: {self.analyzer.format_bytes(usage_info['used'])}")
        print(f"可用空间: {self.analyzer.format_bytes(usage_info['free'])}")
        print(f"使用率: {usage_info['usage_percent']:.1f}%")
        print(f"健康状态: {status_icon} {status}")
        print(f"建议: {message}")
        print()
    
    def print_largest_directories(self, path: str = "/", top_n: int = 20):
        """打印占用空间最大的目录"""
        print("=" * 60)
        print("📊 占用空间最大的目录")
        print("=" * 60)
        
        directories = self.analyzer.analyze_largest_directories(path, top_n=top_n)
        
        if not directories:
            print("❌ 无法分析目录大小")
            return
        
        print(f"显示前 {min(len(directories), top_n)} 个最大的目录:\n")
        
        for i, (dir_path, size) in enumerate(directories, 1):
            size_str = self.analyzer.format_bytes(size)
            percentage = (size / self.analyzer.get_disk_usage(path)['total']) * 100 if self.analyzer.get_disk_usage(path) else 0
            
            print(f"{i:2d}. {dir_path}")
            print(f"    大小: {size_str} ({percentage:.2f}%)")
            print()
    
    def print_system_info(self):
        """打印系统信息"""
        print("=" * 60)
        print("💻 系统信息")
        print("=" * 60)
        
        system_info = self.analyzer.get_system_info()
        
        for key, value in system_info.items():
            print(f"{key}: {value}")
        print()
    
    def export_report(self, output_file: str, path: str = "/"):
        """导出分析报告到JSON文件"""
        print(f"正在生成报告并保存到: {output_file}")
        
        usage_info = self.analyzer.get_disk_usage(path)
        status, message = self.analyzer.get_disk_health_status(usage_info)
        directories = self.analyzer.analyze_largest_directories(path)
        system_info = self.analyzer.get_system_info()
        
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
            ]
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
    
    # 检查路径是否存在
    if not os.path.exists(args.path):
        print(f"❌ 错误: 路径 '{args.path}' 不存在")
        sys.exit(1)
    
    # 创建SpaceCli实例
    space_cli = SpaceCli()
    
    try:
        # 显示系统信息
        if not args.directories_only:
            space_cli.print_system_info()
        
        # 显示磁盘健康状态
        if not args.directories_only:
            space_cli.print_disk_health(args.path)
        
        # 显示目录分析
        if not args.health_only:
            space_cli.print_largest_directories(args.path, args.top_n)
        
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
