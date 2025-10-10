#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpaceCli - macOS 磁盘空间分析工具
模块化版本的主入口文件
"""

import os
import sys
import argparse
from pathlib import Path

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from space_cli import SpaceAnalyzer, SpaceCli, IndexStore


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
        version='SpaceCli 1.5.0'
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
    
    # 将主要执行流程提取为函数，便于交互模式复用
    def run_once(run_args, interactive: bool = False):
        # --home 优先设置路径
        if getattr(run_args, 'home', False):
            run_args.path = str(Path.home())

        # 检查路径是否存在
        if not os.path.exists(run_args.path):
            print(f"❌ 错误: 路径 '{run_args.path}' 不存在")
            if interactive:
                return
            sys.exit(1)

        # 创建SpaceCli实例
        space_cli = SpaceCli()
        # 让 SpaceCli 实例可访问参数（用于索引与提示控制）
        space_cli.args = run_args
        
        try:
            # 显示系统信息
            space_cli.print_system_info()
            
            # 显示磁盘健康状态
            if run_args.health_only:
                space_cli.print_disk_health(run_args.path)
            
            # 显示目录分析
            if run_args.directories_only or run_args.path !='/':
                space_cli.print_largest_directories(run_args.path, run_args.top_n)
                # 若分析路径为当前用户目录，做深度分析
                if os.path.abspath(run_args.path) == os.path.abspath(str(Path.home())):
                    space_cli.print_home_deep_analysis(run_args.top_n)

            # 应用目录分析
            if run_args.apps:
                space_cli.print_app_analysis(run_args.top_n)

            # 大文件分析
            if run_args.big_files:
                space_cli.print_big_files(run_args.path, top_n=run_args.big_files_top, min_size_bytes=run_args.big_files_min_bytes)
            
            # 内存释放优化
            if getattr(run_args, 'memory_cleanup', False):
                space_cli.print_memory_cleanup()
            
            # 导出报告
            if run_args.export:
                space_cli.export_report(run_args.export, run_args.path)
            
            print("=" * 60)
            print("✅ 分析完成！")
            print("=" * 60)
            
        except KeyboardInterrupt:
            print("\n\n❌ 用户中断操作")
            if interactive:
                return
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            if interactive:
                return
            sys.exit(1)
    
    # 交互式菜单：当未传入任何参数时触发（默认执行全部），执行完后返回菜单
    if len(sys.argv) == 1:
        while True:
            print("=" * 60)
            print("🧭 SpaceCli 菜单（直接回车 = 执行全部项目）")
            print("=" * 60)
            home_path = str(Path.home())
            # 动态获取磁盘与内存占用率
            try:
                analyzer_for_menu = SpaceAnalyzer()
                disk_info = analyzer_for_menu.get_disk_usage('/')
                disk_usage_display = f"{disk_info['usage_percent']:.1f}%" if disk_info else "未知"
                sysinfo = analyzer_for_menu.get_system_info()
                mem_usage_display = sysinfo.get("内存使用率", "未知")
            except Exception:
                disk_usage_display = "未知"
                mem_usage_display = "未知"

            print("1) \033[36m执行主要项目（系统信息 + 健康 +  应用）\033[0m")
            print(f"2) \033[36m当前用户目录分析（路径: {home_path}）\033[0m")
            print("3) \033[36m仅显示系统信息\033[0m")
            print(f"4) \033[36m仅显示磁盘健康状态\033[0m  — 当前磁盘占用: \033[33m{disk_usage_display}\033[0m")
            print("5) \033[36m交互式目录空间分析\033[0m")
            print("6) \033[36m仅分析程序应用目录空间\033[0m")
            print("7) \033[36m仅进行大文件分析（比较耗时，可随时终止）\033[0m")
            print(f"8) \033[36m内存释放优化\033[0m  — 当前内存使用率: \033[33m{mem_usage_display}\033[0m")
            print("0) \033[36m退出\033[0m")
            try:
                choice = input("请选择 [回车=1]: ").strip()
            except EOFError:
                choice = ""

            # 重置
            args.health_only = False
            args.directories_only = False
            args.apps = False
            args.big_files = False
            args.memory_cleanup = False
            args.path = '/'

            if choice == "0":
                sys.exit(0)
            elif choice == "2":
                args.path = home_path
                args.directories_only = True
            elif choice == "3":
                pass
            elif choice == "4":
                args.health_only = True
            elif choice == "5":
                args.directories_only = True
            elif choice == "6":
                args.apps = True
            elif choice == "7":
                args.big_files = True
            elif choice == "8":
                args.memory_cleanup = True
            else:
                args.health_only = True
                args.apps = True

            run_once(args, interactive=True)

            try:
                back = input("按回车返回菜单，输入 q 退出: ").strip().lower()
            except EOFError:
                back = ""
            if back == 'q':
                sys.exit(0)
    else:
        # 非交互：按参数执行一次
        run_once(args, interactive=False)


if __name__ == "__main__":
    main()
