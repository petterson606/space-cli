# space-cli - macOS 磁盘空间优化工具

很多人的Mac电脑都会出现磁盘空间不够用，付费软件太贵或者难以使用。

space-cli是一个开源的macOS命令行小工具，用于分析磁盘空间健康度并找出占用空间大的目录，可选择针对单个应用进行一键清理。

本软件采用**最严安全原则**，所有分析操作采用只读模式，未经允许不会尝试改写和破坏用户电脑的任何数据，也不会上传任何数据到外网，严格保护用户的隐私。

## 功能特性

- 🔍 **磁盘健康度检测** - 评估磁盘空间使用情况，提供健康状态建议
- 📊 **交互式目录分析** - 递归分析目录大小，支持选择序号进行深度下探分析
- 💻 **详细系统信息** - 显示CPU、内存、GPU、硬盘等完整硬件信息
- 📄 **报告导出** - 将分析结果导出为JSON格式报告
- ⚡ **高性能优化** - 优先使用 `du -sk` 命令，失败时回退到 `os.scandir` 高效遍历
- 🎯 **灵活配置** - 支持自定义分析路径和显示数量
- 🗂️ **智能索引缓存** - 目录大小结果本地索引缓存（`~/.spacecli/index.json`），支持TTL与重建提示
- 🧩 **应用分析** - 汇总 `Applications`、`Library`、`Caches`、`Logs` 等路径估算应用占用，给出卸载建议
- 🗑️ **一键删除应用** - 在应用分析列表中输入序号即可一键删除所选应用及其缓存（含二次确认）
- 🏠 **用户目录深度分析** - 针对 `~/Library`、`~/Downloads`、`~/Documents` 分别下探并展示Top N目录
- 🗄️ **大文件分析** - 扫描并列出指定路径下最大的文件，支持数量和最小体积阈值
- ⏱️ **支持MCP调用** - 支持你自己的AI Agent无缝调用磁盘空间信息

## 安装

### 方法1：通过 pip 安装（推荐）

```bash
python3 -m pip install --upgrade myspace-cli

# 支持Pip安装
pip install myspace-cli

# 安装完成后直接使用
# 请注意命令行的启动文件名(space-cli)和pip包的名字(myspace-cli)不一样
# 建议直接运行，可以看到使用菜单
space-cli

# 或以模块方式
python3 -m space_cli

# 如果要使用高级的功能，请使用更复杂的命令行参数，可以运行help
space-cli --help

```

### 方法2：直接使用

```bash
# 克隆或下载项目
git clone https://github.com/kennyz/space-cli
cd MacDiskSpace

# 给脚本添加执行权限
chmod +x space_cli.py

# 运行
python3 space_cli.py
```

### 方法3：创建全局命令

```bash
# 复制到系统路径
sudo cp space_cli.py /usr/local/bin/space-cli
sudo chmod +x /usr/local/bin/space-cli

# 现在可以在任何地方使用
space-cli
```

注：若你更倾向于使用 PyPI 包名 `spacecli`，也可执行 `python3 -m pip install --upgrade spacecli`，命令入口同为 `space-cli`。

## 使用方法

### 基本用法

```bash
# 分析根目录（默认）- 支持交互式下探分析
python3 space_cli.py

# 分析指定路径
python3 space_cli.py -p /Users/username

# 显示前10个最大的目录
python3 space_cli.py -n 10

# 快捷分析当前用户目录（含用户目录深度分析）
python3 space_cli.py --home

# 交互式目录空间分析（支持选择序号下探，选择0返回上一级）
python3 space_cli.py --directories-only
```

### 高级用法

```bash
# 只显示磁盘健康状态
python3 space_cli.py --health-only

# 只显示目录分析
python3 space_cli.py --directories-only

# 导出分析报告
python3 space_cli.py --export disk_report.json

# 分析用户目录并导出报告
python3 space_cli.py -p /Users -n 15 --export user_analysis.json

# 使用索引缓存（默认开启）
python3 space_cli.py --use-index

# 强制重建索引
python3 space_cli.py --reindex

# 设置索引缓存有效期为 6 小时
python3 space_cli.py --index-ttl 6

# 非交互，不提示使用缓存
python3 space_cli.py --no-prompt

# 分析应用目录占用并给出卸载建议（按应用归并）
python3 space_cli.py --apps -n 20

# 在应用分析输出后，按提示输入序号一键删除应用（会二次确认）
# 例如：输入 3 即删除列表中的第3个应用及其相关缓存
# 大文件分析（显示前20个，阈值2G）
python3 space_cli.py --big-files --big-files-top 20 --big-files-min 2G

# 将含大文件分析的结果写入导出报告
python3 space_cli.py --big-files --export report.json


```


### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-p, --path` | 要分析的路径 | `/` |
| `-n, --top-n` | 显示前N个最大的目录 | `20` |
| `--health-only` | 只显示磁盘健康状态 | - |
| `--directories-only` | 只显示目录分析 | - |
| `--export FILE` | 导出报告到JSON文件 | - |
| `--use-index` | 使用索引缓存（默认） | - |
| `--no-index` | 禁用索引缓存 | - |
| `--reindex` | 强制重建索引 | - |
| `--index-ttl` | 索引缓存有效期（小时） | `24` |
| `--no-prompt` | 非交互模式，不提示使用缓存 | - |
| `--apps` | 分析应用目录空间与卸载建议 | - |
| `--home` | 将分析路径设置为当前用户目录 | - |
| `--big-files` | 启用大文件分析 | - |
| `--big-files-top` | 大文件列表数量 | `20` |
| `--big-files-min` | 大文件最小阈值（K/M/G/T） | `0` |
| `--version` | 显示版本信息 | - |
| `-h, --help` | 显示帮助信息 | - |

## 输出示例

### 磁盘健康状态
```
============================================================
🔍 磁盘空间健康度分析
============================================================
磁盘路径: /
总容量: 500.0 GB
已使用: 400.0 GB
可用空间: 100.0 GB
使用率: 80.0%
健康状态: ⚠️ 警告
建议: 磁盘空间不足，建议清理一些文件
```

### 交互式目录分析
```
============================================================
📊 占用空间最大的目录
============================================================
显示前 20 个最大的目录:

 1. /Applications --    大小: 15.2 GB (3.04%)
 2. /Users/username/Library --    大小: 8.5 GB (1.70%)
 3. /System --    大小: 6.8 GB (1.36%)

============================================================
🔍 下探分析选项
============================================================
选择序号进行深度分析，选择0返回上一级，直接回车退出:
请输入选择 [回车=退出]: 1

🔍 正在分析: /Applications (15.2 GB)
============================================================
📊 占用空间最大的目录
============================================================
 1. /Applications/Xcode.app --    大小: 8.2 GB (1.64%)
 2. /Applications/Docker.app --    大小: 3.1 GB (0.62%)
 3. /Applications/Visual Studio Code.app --    大小: 1.8 GB (0.36%)
```

### 大文件分析
```
============================================================
🗄️ 大文件分析
============================================================
 1. /Users/username/Downloads/big.iso  --  大小: 7.2 GB (1.44%)
 2. /Users/username/Movies/clip.mov   --  大小: 3.1 GB (0.62%)
```

### 应用分析与一键删除
```
============================================================
🧩 应用目录空间分析与卸载建议
============================================================
 1. Docker Desktop  --  占用: 9.1 GB (1.80%)  — 建议卸载或清理缓存
 2. Xcode           --  占用: 6.2 GB (1.23%)  — 建议卸载或清理缓存
 3. WeChat          --  占用: 2.4 GB (0.47%)  — 可保留，定期清理缓存

是否要一键删除某个应用？输入序号或回车跳过: 1
确认删除应用及相关缓存: Docker Desktop (约 9.1 GB)？[y/N]: y
将尝试删除以下路径：
 - /Applications/Docker.app
 - ~/Library/Application Support/Docker
 - ~/Library/Caches/com.docker.docker
...（略）
✅ 删除完成，预计释放空间: 8.7 GB
```

说明：
- 删除动作包含二次确认，并会列出将删除的路径清单。
- 系统级目录可能因权限/SIP 受保护而无法完全删除，此时工具会尽量清理可删部分并给出失败项与原因。


## MCP Server（可选）

本项目提供 MCP Server，方便在支持 MCP 的客户端中以“工具”的形式调用：

### 安装依赖
```bash
python3 -m pip install mcp
```

### 启动MCP服务
```bash
python3 mcp_server.py
```

### MCP暴露的工具
- `disk_health(path="/")`
- `largest_directories(path="/", top_n=20, use_index=True, reindex=False, index_ttl=24)`
- `app_analysis(top_n=20, use_index=True, reindex=False, index_ttl=24)`
- `big_files(path="/", top_n=20, min_size="0")`

以上工具与 CLI 输出保持一致的逻辑（索引缓存、阈值等），适合与 IDE/Agent 集成。


## 性能优化

- **优先使用 `du -sk` 命令**：在 macOS 上使用原生 `du` 命令快速获取目录大小
- **智能回退机制**：当 `du` 命令失败时，自动回退到基于 `os.scandir` 的高效遍历
- **跳过系统目录**：自动忽略 `/System`、`/Volumes`、`/private` 等系统目录
- **跳过无法访问的文件**：自动处理权限错误和符号链接
- **支持中断操作**：使用 Ctrl+C 随时中断分析
- **内存优化遍历**：使用栈式迭代替代递归，避免深度目录的栈溢出
- **单行滚动进度**：避免输出刷屏，使用 ANSI 清行（\r\033[K）避免长行残留

## 故障排除

### 权限问题
如果遇到权限错误，可以尝试：
```bash
# 使用sudo运行（谨慎使用）
sudo python3 space_cli.py

# 或者分析用户目录
python3 space_cli.py -p /Users/$(whoami)
```

此外，针对“Operation not permitted”等提示：
- 退出相关应用后再试（例如删除 Docker 前先退出 Docker Desktop）。
- 在“系统设置 → 隐私与安全性”中为终端授予“完全磁盘访问权限”。
- 遇到容器元数据或受 SIP 保护的系统级文件（如 `~/Library/Containers/com.docker.docker/... .plist`），可能无法删除，建议仅清理用户级缓存目录。

### 性能问题
对于大型文件系统，分析可能需要较长时间：
- 使用 `--directories-only` 跳过健康检查
- 减少 `-n` 参数值
- 分析特定子目录而不是根目录
 - 使用 `--big-files-min` 提高阈值可减少扫描文件数量
 - 使用 `--use-index`/`--reindex`/`--index-ttl` 控制索引的使用与刷新

## 系统要求

- macOS 10.12 或更高版本
- Python 3.6 或更高版本
- 足够的磁盘空间用于临时文件

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request来改进这个工具！

## 更新日志

### v1.0.0
- 初始版本发布
- 基本的磁盘健康度检测
- 目录大小分析功能
- JSON报告导出
- 命令行参数支持

### v1.1.0
- 新增交互式菜单（无参数时出现），默认执行全部项目
- 新增 `--home` 用户目录快速分析与用户目录深度分析
- 新增应用分析缓存（`~/.cache/spacecli/apps.json`）
- 新增大文件分析 `--big-files`/`--big-files-top`/`--big-files-min`
- 导出报告在启用大文件分析时包含 `largest_files`
- 单行滚动进度显示

### v1.2.0
- 应用分析支持"按序号一键删除应用"，并显示将删除的路径清单与预计释放空间
- 删除过程增加权限修复与降级清理策略（chflags nouchg / chmod 0777 / 逐项清理）
- 针对 "Operation not permitted" 增加友好提示（SIP、完全磁盘访问、退出相关应用）
- 单行覆盖输出加入 ANSI 清行，避免长行残留

### v1.3.0
- **性能大幅优化**：优先使用 `du -sk` 命令获取目录大小，失败时回退到 `os.scandir` 高效遍历
- **交互式下探分析**：支持选择序号进行深度目录分析，选择0返回上一级
- **增强系统信息**：显示 CPU、内存、GPU、硬盘等完整硬件信息
- **智能目录过滤**：自动忽略系统目录（`/System`、`/Volumes`、`/private`）
- **优化用户体验**：改进菜单选项，支持交互式目录空间分析
