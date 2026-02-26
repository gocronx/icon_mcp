# icon_mcp

基于 MCP (Model Context Protocol) 的图标服务器，用于从 iconfont.cn 搜索和获取图标。

## 功能特性

- 🔍 **图标搜索**: 从 iconfont.cn 搜索图标
- 🎨 **SVG 获取**: 获取图标的 SVG 格式内容
- ⚡ **缓存机制**: 内置内存缓存，30分钟过期
- 🖥️ **Web 界面**: 提供可视化图标选择和保存功能（HTTP + WebSocket）
- 🌐 **多语言**: 支持中文 (zh-CN) 和英文 (en)
- 📦 **类型安全**: 使用 Pydantic 数据模型
- 🔄 **全异步**: 基于 asyncio / aiohttp / httpx

## 技术栈

| 组件 | 技术 |
|------|------|
| MCP 协议 | `mcp` Python SDK (stdio transport) |
| HTTP 服务 | `aiohttp` (HTTP + WebSocket) |
| HTTP 客户端 | `httpx` (异步请求 iconfont.cn API) |
| 数据模型 | `pydantic` |
| 包管理 | `uv` |
| Python 版本 | >= 3.10 |

## 安装

```bash
# 使用 uv 初始化虚拟环境并安装依赖
uv sync

# 或者直接安装
uv pip install -e .
```

## 使用方法

### 1. 直接运行（推荐）
```bash
uv run python run.py
uv run python run.py --port 8080 --language zh-CN
```

### 2. 使用命令行入口
```bash
uv run icon-mcp
```

### 3. 使用模块方式运行
```bash
uv run python -m icon_mcp
```

### 4. 自定义端口运行
```bash
uv run python run.py --port 8080
uv run python run.py --port 8080 --language zh-CN --auto-start-web --auto-open
```

### 4. 环境变量配置
```bash
export LANGUAGE=zh-CN
export WEB_SERVER_PORT=8080
export WEB_SERVER_AUTO_OPEN=true
export AUTO_START_WEB_SERVER=true
```

### 5. 命令行参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--port` | Web 服务器端口 | 3000 |
| `--language` | 界面语言 (`en` / `zh-CN`) | en |
| `--auto-start-web` | 启动时自动开启 Web 服务器 | false |
| `--auto-open` | 自动打开浏览器 | false |

## 编辑器集成

### Claude Code（命令行）

通过 `claude mcp add` 命令一键添加：

```bash
# 基本用法
claude mcp add icon-mcp -- uv --directory /path/to/icon_mcp run python run.py

# 指定自定义端口
claude mcp add icon-mcp -- uv --directory /path/to/icon_mcp run python run.py --port 8080

# 中文 + 自定义端口 + 自动启动 Web
claude mcp add icon-mcp -- uv --directory /path/to/icon_mcp run python run.py --port 8080 --language zh-CN --auto-start-web

# 添加后查看已注册的 MCP
claude mcp list
```

> **注意**: 将 `/path/to/icon_mcp` 替换为项目实际路径。

### Cursor / Claude Desktop 配置（JSON）

在 `.cursor/mcp.json` 或 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "icon": {
      "command": "uv",
      "args": ["--directory", "/path/to/icon_mcp", "run", "python", "run.py", "--port", "8080"],
      "env": {
        "LANGUAGE": "zh-CN"
      }
    }
  }
}
```

## MCP 工具列表

| 工具名称 | 描述 |
|----------|------|
| `search_icons` | 从 iconfont.cn 搜索图标 |
| `start_web_server` | 启动 Web 图标选择界面 |
| `stop_web_server` | 停止 Web 服务器 |
| `check_selection_status` | 轮询检查用户图标选择状态 |
| `get_cache_stats` | 获取缓存统计信息 |
| `clear_cache` | 清除缓存 |
| `save_icons` | 保存图标 SVG 到本地文件 |

## 项目结构

```
icon_mcp/
├── pyproject.toml           # 项目配置 (uv/hatch)
├── README.md
└── src/
    └── icon_mcp/
        ├── __init__.py      # 包信息
        ├── __main__.py      # 入口点 (python -m icon_mcp)
        ├── server.py        # MCP Server 核心 (工具注册 & 调度)
        ├── config.py        # 配置管理
        ├── models.py        # Pydantic 数据模型
        ├── utils/
        │   ├── cache.py     # 缓存管理器
        │   ├── search.py    # 图标搜索逻辑
        │   ├── saver.py     # 图标保存
        │   └── web_server.py # HTTP + WebSocket 服务器
        ├── web/
        │   └── interface.py # Web UI HTML/JS 生成
        └── lang/
            ├── __init__.py  # i18n 核心 (t() 翻译函数)
            ├── en.py        # 英文翻译
            └── zh_cn.py     # 中文翻译
```

## 贡献

欢迎提交 Pull Request 来改进这个项目！如果你觉得这个项目有帮助，请给一个 ⭐ Star 支持一下。