# 漫镜工场 ManJu Studio · 本地部署指南

## 一、环境要求

部署前请确认目标电脑满足以下条件：

| 依赖 | 最低版本 | 说明 |
|------|---------|------|
| **操作系统** | Windows 10 64 位 | 当前版本针对 Windows 优化 |
| **Python** | 3.10+ | 后端运行时；安装时务必勾选 "Add Python to PATH" |
| **Node.js** | 18+（推荐 20 LTS） | 前端运行时；含 npm |
| **npm** | 9+ | 随 Node.js 安装 |
| **浏览器** | Chrome / Edge | 访问前端工作台 |

**下载地址：**
- Python：https://www.python.org/downloads/
- Node.js：https://nodejs.org/（选 LTS 版本）

---

## 二、一键部署（推荐）

### 方式 A：双击运行

1. 将整个项目文件夹复制到目标电脑
2. 双击 **`deploy.bat`**
3. 脚本自动完成：环境检查 → 装依赖 → 初始化 → 启动
4. 部署完成后浏览器自动打开 `http://localhost:3000`

### 方式 B：命令行运行

```powershell
# 完整部署并启动
powershell -ExecutionPolicy Bypass -File deploy.ps1

# 仅部署不启动
powershell -ExecutionPolicy Bypass -File deploy.ps1 -SkipStart

# 仅检查环境是否满足（不执行部署）
powershell -ExecutionPolicy Bypass -File deploy.ps1 -CheckOnly
```

### 部署脚本做了什么

| 步骤 | 操作 | 耗时 |
|------|------|------|
| 1 | 检查 Python / Node.js / npm 是否安装 | 即时 |
| 2 | 创建 Python 虚拟环境 `.venv`，安装后端依赖 | ~1 分钟 |
| 3 | 安装前端依赖（`npm install`） | ~2-3 分钟 |
| 4 | 从 `.env.example` 生成 `.env` 配置文件 | 即时 |
| 5 | 初始化 SQLite 数据库（自动建表+迁移） | ~3 秒 |
| 6 | 启动后端(8000) + 前端(3000) + 打开浏览器 | ~10 秒 |

---

## 三、手动部署（分步执行）

如果一键脚本失败，可按以下步骤手动操作。

### 3.1 安装后端依赖

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3.2 生成配置文件

```powershell
cd backend
copy .env.example .env
```

编辑 `.env`，按需修改（详见下文「配置说明」）。

### 3.3 安装前端依赖

```powershell
cd frontend
npm install
```

### 3.4 初始化数据库

```powershell
cd backend
.venv\Scripts\python.exe -c "from app.database import Base, engine; from app.models import *; from app.migrations import run_migrations; from app.storage import ensure_dirs; Base.metadata.create_all(bind=engine); run_migrations(); ensure_dirs(); print('OK')"
```

### 3.5 启动平台

**方式 1：一键启动器（推荐）**

双击项目根目录的 `start_manju.bat`，自动启动前后端并打开浏览器。

**方式 2：手动分别启动**

终端 1（后端）：
```powershell
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

终端 2（前端）：
```powershell
cd frontend
npm run dev
```

浏览器打开：http://localhost:3000

---

## 四、配置说明（backend/.env）

### 4.1 模拟模式 vs 真实模式

| 模式 | MOCK_MODE | API Key | 说明 |
|------|-----------|--------|------|
| **模拟模式** | `true` | 不需要 | 全流程可演示，AI 输出为模拟内容，零成本 |
| **真实模式** | `false` | 必填 | 调用真实 AI 厂商，产生实际费用 |

**首次部署建议先用模拟模式体验，再切换真实模式。**

### 4.2 真实模式所需 API Key

| API | 申请地址 | 用途 | 费用 |
|-----|---------|------|------|
| **DeepSeek** | https://platform.deepseek.com/ | 文本生成（小说/剧本/分镜） | 按 token 计费，V4 Flash 便宜 |
| **阿里云百炼** | https://bailian.console.aliyun.com/ | 图像/视频/TTS | 套餐或按量计费 |

**阿里云百炼有两种 Key：**
- `sk-sp-` 开头（套餐 Key）：有 QPS 限制，适合 TTS
- `sk-ws-` 开头（按量计费 Key）：不限流，推荐用于图像/视频

### 4.3 关键配置项

```ini
# 模式开关（true=模拟 / false=真实）
MOCK_MODE=true

# DeepSeek 文本模型（真实模式必填）
DEEPSEEK_API_KEY=sk-xxxxxxxx
DEEPSEEK_MODEL=deepseek-v4-flash

# 阿里云百炼（图像/视频/TTS）
DASHSCOPE_API_KEY=sk-sp-xxxxxxx
DASHSCOPE_IMAGE_MODEL=wan2.7-image-pro
DASHSCOPE_VIDEO_MODEL=happyhorse-1.1-i2v

# 按量计费 Key（可选，避免套餐限流）
DASHSCOPE_PAY_API_KEY=sk-ws-xxxxxxx

# JWT 密钥（生产请改为随机字符串）
JWT_SECRET=please-change-me-in-production
```

### 4.4 前端配置（frontend/.env.local）

```
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

仅当后端不在 localhost:8000 时需要修改。

---

## 五、日常使用

### 启动平台

双击 **`start_manju.bat`** → 浏览器自动打开。

启动器功能：
- 深色 UI 提示框显示启动进度
- 就绪后自动打开浏览器
- 闲置 5 分钟自动关闭（节省资源）
- 可手动「停止」/「停止后重试」

### 停止平台

- 关闭启动器提示框（UI 模式会停止服务）
- 或终端执行：`powershell -File start_manju.ps1 -Command stop`

### 查看运行状态

```powershell
powershell -File start_manju.ps1 -Command check
```

### 重置数据库

如需清空数据重新开始：

```powershell
cd backend
del manju.db
.venv\Scripts\python.exe -c "from app.database import Base, engine; from app.models import *; from app.storage import ensure_dirs; Base.metadata.create_all(bind=engine); ensure_dirs(); print('已重置')"
```

---

## 六、验证部署成功

1. 打开浏览器访问 http://localhost:3000
2. 看到登录页面（漫镜工场品牌页）
3. 点击「注册」，创建账号
4. 进入工作台，点击「+ 新建」创建项目
5. 在「小说生成」填入题材/主角，点击「AI 生成小说」
   - 模拟模式：~2 秒返回模拟内容
   - 真实模式：~1 分钟返回真实 AI 生成的小说
6. 如果以上步骤全部正常，部署成功

### 后端健康检查

```powershell
curl http://localhost:8000/api/health
```

返回示例：
```json
{"status":"ok","app":"漫镜工场 ManJu Studio API","mock_mode":true,"version":"1.3.0"}
```

---

## 七、常见问题

### Q1：双击 deploy.bat 闪退

右键 `deploy.bat` → 以管理员身份运行；或打开 PowerShell 执行：
```powershell
Set-ExecutionPolicy Bypass -Scope CurrentUser
.\deploy.ps1
```

### Q2：Python 找不到

安装 Python 时务必勾选 **"Add Python to PATH"**。如已安装但找不到，重启电脑或手动将 Python 路径加入系统 PATH。

### Q3：npm install 很慢

切换国内镜像源：
```powershell
npm config set registry https://registry.npmmirror.com
```
然后重新执行 `npm install`。

### Q4：pip install 很慢

使用国内镜像源：
```powershell
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q5：端口被占用

后端默认 8000，前端默认 3000。如端口被占用：
- 停止占用进程：`powershell -File start_manju.ps1 -Command stop`
- 或修改 `start_manju.ps1` 顶部的端口参数

### Q6：真实模式下图像生成失败（429 限流）

阿里云套餐 Key（sk-sp-）有 QPS 限制。解决方案：
- 配置按量计费 Key（sk-ws-）到 `DASHSCOPE_PAY_API_KEY`
- 按量计费 Key 不限流，走 `dashscope.aliyuncs.com` 通用域名

### Q7：图生视频失败

图生视频需要关键帧为公网可访问 URL。本地开发环境平台已自动复用万相返回的原始公网 URL，通常无需额外配置。如仍有问题，确认 `DASHSCOPE_PAY_API_KEY` 已正确配置。

### Q8：切换到 PostgreSQL（可选）

默认 SQLite 开箱即用。如需 PostgreSQL，在 `.env` 中：
```ini
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/manju
```
并安装驱动：`pip install psycopg-binary`

---

## 八、项目目录结构

```
AI漫剧平台trae版/
├── deploy.bat                  # 一键部署（双击运行）
├── deploy.ps1                  # 一键部署脚本
├── start_manju.bat             # 一键启动（双击运行）
├── start_manju.ps1             # 启动器（UI+闲置关闭）
├── DEPLOY.md                   # 本文档
│
├── backend/
│   ├── .env.example            # 配置模板（复制为 .env）
│   ├── .env                    # 实际配置（gitignore，不入库）
│   ├── requirements.txt        # Python 依赖
│   ├── manju.db                # SQLite 数据库（自动生成）
│   ├── .venv/                  # Python 虚拟环境（自动生成）
│   ├── storage/                # 生成资产（图片/视频/音频）
│   └── app/
│       ├── main.py             # FastAPI 入口
│       ├── config.py           # 配置类 + 模型目录
│       ├── database.py         # 数据库引擎
│       ├── migrations.py       # 数据库迁移（幂等）
│       ├── storage.py          # 资产存储
│       ├── models.py           # 数据模型
│       ├── api/                # API 路由（14 个模块）
│       ├── gateway/            # AI 厂商网关
│       │   ├── providers/      # DeepSeek / 万相图像 / 万相视频 / TTS
│       │   └── prompt_builder.py  # 集中提示词控制
│       └── tasks/              # 异步任务编排
│
└── frontend/
    ├── .env.local.example      # 前端配置模板
    ├── package.json            # Node 依赖
    ├── app/                    # Next.js 页面
    ├── components/             # UI 组件
    ├── lib/                    # API 客户端
    └── store/                  # 全局状态
```

---

## 九、技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 后端 | FastAPI + SQLAlchemy 2.x + Pydantic 2.x | Python 3.10+ |
| 前端 | Next.js 14 + React 18 + Zustand + Tailwind CSS | Node 18+ |
| 数据库 | SQLite（默认）/ PostgreSQL（可选） | - |
| AI 文本 | DeepSeek V4 Flash（OpenAI 兼容接口） | - |
| AI 图像 | 通义万相 2.7（DashScope） | - |
| AI 视频 | HappyHorse 1.1 图生视频（DashScope） | - |
| AI 语音 | Qwen-Audio TTS（DashScope） | - |

---

如有问题，查看启动日志：`manju_launcher.log`（项目根目录）。
