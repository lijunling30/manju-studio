# 漫镜工场 ManJu Studio · AI 漫剧工业化生产平台

> 从一句话题材到可发布成片 —— 一条打通的 AI 漫剧自动化生产流水线

**漫镜工场**是一个面向 AI 漫剧（漫画剧）生产的全栈平台，把「小说 → 剧本 → 角色 → 分镜 → 关键帧 → 视频 → 配音 → 成片」的完整链路做成了可视化工作台。核心主张是 **AI 负责生成，人负责选择和管理**：每一次付费 AI 调用前都先结构化复述需求并预估成本，用户确认之后才真正执行，**确认之前零计费**。

| | |
|---|---|
| 后端 | Python 3.10+ · FastAPI · SQLAlchemy 2.x · Pydantic 2.x · 14 个 API 模块 |
| 前端 | Next.js 14（App Router）· React 18 · Zustand · Tailwind CSS · 12 个页面 |
| 数据 | SQLite（开发，开箱即用）/ PostgreSQL（生产，一行配置切换）· 15 张数据表 |
| 任务编排 | 进程内 asyncio Worker（演示版 Celery 语义）· 状态机 + 指数退避 + 厂商降级 |
| 真实 AI 厂商 | DeepSeek V4 Flash（文本）· 通义万相 2.7（图像）· HappyHorse 1.1 i2v（视频）· Qwen-Audio TTS（语音） |
| 双模式 | `MOCK_MODE=true` 零配置零成本跑通全流程 / `false` 接入真实厂商生产 |

---

## 界面预览

<table>
  <tr>
    <td align="center"><img src="平台截图/01_登录页.png" width="260"><br><sub>登录 / 注册</sub></td>
    <td align="center"><img src="平台截图/02_仪表盘.png" width="260"><br><sub>仪表盘（9 步流程入口）</sub></td>
    <td align="center"><img src="平台截图/03_角色资产库.png" width="260"><br><sub>角色资产库</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="平台截图/04_角色详情卡片.png" width="260"><br><sub>角色三视图 + 表情抽卡</sub></td>
    <td align="center"><img src="平台截图/05_剧本编辑器.png" width="260"><br><sub>剧本编辑器</sub></td>
    <td align="center"><img src="平台截图/06_分镜时间线.png" width="260"><br><sub>分镜时间线</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="平台截图/07_关键帧抽卡.png" width="260"><br><sub>关键帧抽卡（含 AI 评分）</sub></td>
    <td align="center"><img src="平台截图/08_视频生成.png" width="260"><br><sub>多镜头视频生成</sub></td>
    <td align="center"><img src="平台截图/09_剪辑合成导出.png" width="260"><br><sub>剪辑合成与导出</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="平台截图/10_设置_模型服务.png" width="260"><br><sub>模型服务设置</sub></td>
    <td></td>
    <td></td>
  </tr>
</table>

---

## 核心特性

- **9 步流水线**：小说生成 → 剧本结构化 → 角色资产库 → 分镜设计 → 关键帧抽卡 → 视频生成 → 配音音效 → 剪辑合成 → 成片导出，全程可视化操作。
- **需求确认闸口（成本安全闸）**：所有 AI 生成/编辑请求，先复述需求 + 预估成本，用户点「确认执行」后才调用付费接口；未确认不产生任何费用。
- **候选抽卡机制**：角色三视图、表情集、关键帧均一次生成多个候选并附 AI 评分，由用户挑一个确认，而不是让 AI 替你决定。
- **模型服务自选**：文本 / 图像 / 视频 / TTS 四类模型均可由用户在设置页自由选择，留空即回退系统默认。
- **角色一致性**：角色资产库 + 特征描述块 + 同 seed 联动，缓解同一角色跨镜头「变脸」问题。
- **成本全透明**：镜头级记账（用户 × 项目 × 模块 × 镜头四维），预算使用 80% 预警、100% 拦截。
- **合规底线**：导出成片强制携带 AI 生成标识（无开关）；内容安全审核作为可选模块，由用户决定是否启用。
- **双模式运行**：模拟模式内置 8 个 Mock 厂商，无需任何 API Key 即可完整体验；真实模式仅需替换厂商适配器。

---

## 系统架构

```mermaid
graph TD
    subgraph L1["L1 前端工作台 · Next.js 14"]
        UI1[登录 / 仪表盘]
        UI2[9 步流水线页面]
        UI3[确认卡 ConfirmCard]
        UI4[任务中心 TaskCenter]
    end

    subgraph L2["L2 API 层 · FastAPI（14 模块）"]
        API[auth / projects / novels / scripts / shots<br/>characters / keyframes / video_tasks / audio<br/>final_videos / costs / ai_requests / tasks / model_settings]
    end

    subgraph L3["L3 服务层"]
        GATE[确认闸口 core/gate.py]
        DISPATCH[任务派发 api/dispatch.py]
        WORKER[编排 Worker tasks/worker.py]
    end

    subgraph L4["L4 AI 模型网关 ★核心自研★"]
        GW[router.py 统一门面]
        PB[prompt_builder.py 提示词控制]
        COST[core/costs.py 成本模型]
    end

    subgraph L5["L5 厂商适配层"]
        P1[DeepSeek 文本]
        P2[通义万相 图像]
        P3[HappyHorse 视频]
        P4[Qwen-Audio TTS]
        P5[Mock 厂商 × 8]
    end

    subgraph L6["L6 基础设施"]
        DB[(SQLite / PostgreSQL)]
        FS[storage/ 生成资产]
    end

    L1 --> L2 --> L3 --> L4 --> L5
    L3 --> DB
    L5 --> FS
```

**架构原则：业务层禁止直连厂商，一律经过 AI 模型网关。** 网关统一屏蔽各家同步 / 异步接口差异，向下负责模型路由与降级、成本预估与记账、中文提示词到厂商提示词的静默转换。

---

## 核心机制

### 1. 确认闸口（成本安全闸）

闸口判定逻辑位于 [gate.py](backend/app/core/gate.py)，优先级从高到低：

```
≥50 元（高成本护栏）  → 强制确认
≥20 镜头（批量护栏）  → 强制确认
全局开关关闭          → 免确认
模块级开关关闭        → 免确认
会话级开关关闭        → 免确认
其余情况              → 默认需要确认
```

> **护栏优先级最高**：即使把三级开关全部关闭，高成本或批量任务仍会强制弹出确认卡，防止误操作烧钱。

确认卡状态机：`draft → confirmed / rejected / bypassed / cancelled / timeout`

- 用户可对复述结果点「修改」要求 AI 重新复述，最多 3 轮，超过则转人工；
- 60 秒未确认自动超时取消，**不产生费用**；
- 会话级开关存于内存，刷新即恢复安全态，避免被永久关闭。

### 2. AI 模型网关

| 模块 | 厂商优先级（主 → 备） | 调用形态 |
|---|---|---|
| 文本（小说 / 剧本 / 分镜） | `deepseek_v3` → `qwen_max` | 同步 |
| 图像（角色 / 关键帧） | `wanxiang` → `jimeng` | 异步任务 |
| 视频 | `vidu_q3` → `seedance_2_0` → `kling_2_0` | 异步任务 |
| TTS | `doubao_tts` → `cosyvoice` | 同步 |
| 内容安全 | `aliyun_sec` | 同步 |

主厂商失败后自动切换到备选（循环队列），切换点集中在网关层，业务代码无感知。

### 3. 任务编排（状态机 + 指数退避）

```
queued → running → success
                ↘ failed → retrying → running（2s / 4s / 8s）
                         ↘ 重试 3 次仍失败 → manual_review（人工介入）
```

- **并发限制**：Worker 同时处理 2 个任务，避免触发厂商 API 429 限流；
- **超时清扫**：60 秒未确认的闸口记录自动置为 `timeout`，零费用泄漏；
- **卡死兜底**：`running` 超过 30 分钟且无对应协程的任务转 `manual_review`。

### 4. 成本模型

成本预估以「单价 × 数量」为核心，向上向下浮动给出区间：

```
C_low  = 0.9 × 单价 × 数量
C_high = 1.2 × 单价 × 数量
```

预算护栏判定（`S` = 已花费，`L` = 预算上限）：

```
拦截  ⟸  S ≥ L  或  (S + C_high) / L ≥ 1
预警  ⟸  0.8 ≤ S / L < 1
```

### 5. 角色一致性

- 所有涉及角色的生成都引用同一份角色特征块，强制约束发型 / 发色 / 瞳色 / 面部特征 / 服饰 / 体型不变；
- 表情集使用与「选中的三视图」**相同的 seed**，保证同源；
- 关键帧 seed 计算：`seed = shot_id × 100 + round × 10 + index`。

---

## 目录结构

```
AI漫剧平台trae版/
├── backend/                     # 后端（FastAPI）
│   ├── app/
│   │   ├── api/                 # 14 个 REST 模块 + dispatch.py 任务派发
│   │   ├── core/                # gate.py 确认闸口 / costs.py 成本模型
│   │   ├── gateway/             # ★AI 模型网关
│   │   │   ├── router.py        #   统一门面（路由 / 双模式切换）
│   │   │   ├── base.py          #   厂商抽象基类与数据结构
│   │   │   ├── prompt_builder.py#   提示词控制（一致性）
│   │   │   └── providers/       #   4 个真实厂商 + 8 个 Mock 厂商
│   │   ├── tasks/               # worker.py 编排 Worker / jobs.py 任务逻辑
│   │   ├── models.py            # 15 张表 SQLAlchemy 模型
│   │   ├── schemas.py           # Pydantic 请求 / 响应
│   │   ├── security.py          # JWT 鉴权
│   │   ├── migrations.py        # 幂等数据库迁移（自动补列）
│   │   └── main.py              # 应用入口
│   ├── scripts/                 # 冒烟测试 / 环境诊断 / 演示数据
│   ├── tests/                   # pytest 用例
│   └── requirements.txt
├── frontend/                    # 前端（Next.js 14）
│   ├── app/(auth)/login         # 登录 / 注册
│   ├── app/(workspace)/         # 仪表盘 / 剧本 / 角色 / 分镜 / 抽卡 / 视频 / 配音 / 导出 / 成本 / 设置
│   ├── components/              # 确认卡 / 任务中心 / 侧边栏 / 项目弹窗
│   ├── lib/                     # API 客户端 / useConfirmGate 闸口 Hook
│   ├── store/                   # Zustand 状态
│   └── styles/tokens.css        # 设计 Token（深色影院级 + 亮色双主题）
├── 平台截图/                    # 10 张全流程实测界面截图
├── deploy.bat / deploy.ps1      # 一键部署（环境检查 → 装依赖 → 初始化 → 启动）
├── start_manju.bat / .ps1       # 日常启动（含闲置自动关闭守护）
├── DEPLOY.md                    # 部署指南
├── 使用说明.md                  # 平台操作手册
└── 项目报告.md                  # 项目深度报告（架构 / 机制 / 数据模型）
```

---

## 快速开始

### 环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| 操作系统 | Windows 10/11 64 位 | 启动脚本为 PowerShell 编写 |
| Python | 3.10+ | 安装时勾选 Add Python to PATH |
| Node.js | 18+（推荐 20 LTS） | 含 npm |
| 浏览器 | Chrome / Edge | — |

### 方式一：一键部署（推荐）

```text
1. 双击 deploy.bat
2. 脚本自动完成：环境检查 → 创建虚拟环境 → 装依赖 → 写配置 → 建库 → 启动
3. 浏览器自动打开 http://localhost:3000
```

### 方式二：手动部署

```powershell
# ① 后端依赖
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# ② 配置文件
copy .env.example .env      # 首次可保持 MOCK_MODE=true，无需任何 API Key

# ③ 前端依赖
cd ..\frontend
npm install

# ④ 初始化数据库
cd ..\backend
.venv\Scripts\python.exe init_db.py

# ⑤ 启动（两个终端）
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000   # 后端 + Swagger
npm run dev                                                            # 前端（在 frontend 目录）
```

启动后：

- 前端工作台：<http://localhost:3000>
- API 文档（Swagger）：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/api/health>

### 日常启动

双击 `start_manju.bat` 即可（带启动进度框，闲置一段时间会自动关闭释放资源）。

---

## 配置说明

配置文件为 `backend/.env`（由 `backend/.env.example` 复制而来）。

### 双模式开关

```ini
MOCK_MODE=true    # true = 模拟厂商，零配置零成本演示全流程
                  # false = 接入真实 AI 厂商（需填写下方 Key）
```

### 真实模式所需 Key

```ini
# 文本：DeepSeek 官方（https://platform.deepseek.com/）
DEEPSEEK_API_KEY=sk-xxxxxxxx
DEEPSEEK_MODEL=deepseek-v4-flash

# 图像 / 视频 / TTS：阿里云百炼（https://bailian.console.aliyun.com/）
DASHSCOPE_API_KEY=sk-sp-xxxxxxx        # 套餐 Key（TTS 用）
DASHSCOPE_PAY_API_KEY=sk-ws-xxxxxxx    # 按量 Key（图像/视频用，不限流）
DASHSCOPE_IMAGE_MODEL=wan2.7-image-pro
DASHSCOPE_VIDEO_MODEL=happyhorse-1.1-i2v
```

> **为什么要两个 Key**：套餐 Key 有 QPS 限制，图像 / 视频高频调用容易触发 429；按量计费 Key 走通用域名不限流。代码层自动路由，无需手动切换。

### 其他可调项

```ini
JWT_SECRET=please-change-me-in-production   # 生产环境务必改为随机长字符串
GATE_TIMEOUT_SECONDS=60                     # 确认卡超时时间
GATE_HIGH_COST_THRESHOLD=50                 # 高成本强制确认阈值（元）
GATE_BATCH_THRESHOLD=20                     # 批量强制确认阈值（镜头数）
# DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/manju  # 切 PostgreSQL
```

---

## 测试

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/ -v
```

测试覆盖：注册登录与 JWT、确认闸口全链路（确认 / 驳回 / 取消 / 超时 / 高成本护栏）、成本模型与预算护栏、端到端流水线。

辅助脚本：

| 脚本 | 用途 |
|---|---|
| `backend/scripts/smoke_test.py` | 部署后冒烟验证 |
| `backend/scripts/diagnose.py` | 环境诊断 |
| `backend/scripts/db_check.py` | 数据库健康检查 |
| `backend/scripts/seed_demo.py` | 填充演示数据 |

---

## 文档索引

- [使用说明.md](使用说明.md) — 平台操作手册：9 步流水线逐步操作、闸口与成本设置、常见问题
- [DEPLOY.md](DEPLOY.md) — 部署指南：一键 / 手动部署、配置说明、故障排查
- [项目报告.md](项目报告.md) — 项目深度报告：架构全景、核心机制公式、数据模型、接入细节

---

## 说明

- **本项目为个人独立开发的作品项目**，用于学习与实践 AI 应用工程，代码开源供学习参考。
- 仓库内**不含任何 API Key**，`backend/.env` 已被 `.gitignore` 排除，请勿提交自己的密钥。
- 模拟模式下生成的图片 / 视频 / 音频均为占位资源，仅用于演示流程；真实模式生成内容由对应 AI 厂商产出，使用时请遵守各厂商服务条款。
- 导出成片强制携带 AI 生成标识，请勿移除后用于可能误导他人的场景。