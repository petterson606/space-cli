#!/bin/bash
# SpaceCli 安装脚本

set -e

echo "🚀 SpaceCli 安装程序"
echo "===================="

# 检查Python版本
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到Python3，请先安装Python3"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ 检测到Python版本: $PYTHON_VERSION"

# 检查是否为macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "⚠️  警告: 此工具专为macOS设计，在其他系统上可能无法正常工作"
fi

# 获取安装目录
INSTALL_DIR="/usr/local/bin"
SCRIPT_NAME="space-cli"

echo ""
echo "选择安装方式:"
echo "1) 全局安装 (推荐) - 安装到 $INSTALL_DIR"
echo "2) 用户安装 - 安装到 ~/bin"
echo "3) 仅复制文件 - 不创建全局命令"
echo ""

read -p "请选择 (1-3): " choice

case $choice in
    1)
        echo "🔧 执行全局安装..."
        if [[ $EUID -ne 0 ]]; then
            echo "需要管理员权限，请输入密码:"
            sudo cp space_cli.py "$INSTALL_DIR/$SCRIPT_NAME"
            sudo chmod +x "$INSTALL_DIR/$SCRIPT_NAME"
        else
            cp space_cli.py "$INSTALL_DIR/$SCRIPT_NAME"
            chmod +x "$INSTALL_DIR/$SCRIPT_NAME"
        fi
        echo "✅ 已安装到 $INSTALL_DIR/$SCRIPT_NAME"
        echo "现在可以在任何地方使用: $SCRIPT_NAME"
        ;;
    2)
        echo "🔧 执行用户安装..."
        USER_BIN="$HOME/bin"
        mkdir -p "$USER_BIN"
        cp space_cli.py "$USER_BIN/$SCRIPT_NAME"
        chmod +x "$USER_BIN/$SCRIPT_NAME"
        echo "✅ 已安装到 $USER_BIN/$SCRIPT_NAME"
        
        # 检查PATH
        if [[ ":$PATH:" != *":$USER_BIN:"* ]]; then
            echo ""
            echo "⚠️  请将以下行添加到您的shell配置文件 (~/.zshrc 或 ~/.bash_profile):"
            echo "export PATH=\"\$HOME/bin:\$PATH\""
            echo ""
            echo "然后运行: source ~/.zshrc (或 source ~/.bash_profile)"
        fi
        ;;
    3)
        echo "📁 仅复制文件..."
        CURRENT_DIR=$(pwd)
        echo "✅ 文件已准备就绪: $CURRENT_DIR/space_cli.py"
        echo "使用方法: python3 $CURRENT_DIR/space_cli.py"
        ;;
    *)
        echo "❌ 无效选择"
        exit 1
        ;;
esac

echo ""
echo "🎉 安装完成！"
echo ""
echo "使用方法:"
echo "  $SCRIPT_NAME                    # 分析根目录"
echo "  $SCRIPT_NAME -p /Users          # 分析用户目录"
echo "  $SCRIPT_NAME -n 10              # 显示前10个最大目录"
echo "  $SCRIPT_NAME --help             # 显示帮助信息"
echo ""
echo "更多信息请查看 README.md"
