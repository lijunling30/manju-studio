# 漫镜工场 · ManJu Studio

> AI 漫剧工业化生产平台 — 从小说到成片的一站式流水线

小说 → 剧本 → 角色 → 分镜 → 关键帧 → 视频 → 配音 → 成片，全流程 AI 自动化，用户只需选择和管理。

## ✨ 核心特性

- **9 步流水线**：小说生成 → 剧本结构化 → 角色资产库 → 分镜设计 → 关键帧抽卡 → 视频生成 → 配音音效 → 剪辑合成 → 成片导出
- **确认闸口**：每次 AI 调用前复述需求 + 成本预估，用户确认后才执行，未确认零计费
- **候选抽卡**：角色三视图 / 关键帧均生成候选供用户选择，AI 自动生成、用户负责管理
- **模型服务设置**：用户可为每个模块自主选择 AI 模型（文本/图像/视频/TTS）
- **AI 标识强制**：所有导出成片强制携带 AI 生成标识（合规底线）
- **双模式**：模拟模式（零配置演示全流程）/ 真实模式（接入真实 AI 厂商）

## 🚀 快速开始

### 一键部署

1. 确保 Python 3.10+ 和 Node.js 18+ 已安装
2. 双击 `deploy.bat`
3. 脚本自动完成环境配置和依赖安装
4. 浏览器自动打开 http://localhost:3000

### 日常启动

双击 `start_manju.bat` 即可。

详细部署说明见 [DEPLOY.md](./DEPLOY.md)。

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI · SQLAlchemy 2.x · Pydantic 2.x |
| 前端 | Next.js 14 · React 18 · Zustand · Tailwind CSS |
| 数据库 | SQLite（默认）/ PostgreSQL（可选） |
| AI 文本 | DeepSeek V4 Flash |
| AI 图像 | 通义万相 2.7 |
| AI 视频 | HappyHorse 1.1 |
| AI 语音 | Qwen-Audio TTS |

## 📁 项目结构

```
AI漫剧平台trae版/
├── deploy.bat / deploy.ps1      # 一键部署
├── start_manju.bat / .ps1       # 一键启动
├── DEPLOY.md                    # 部署指南
├── backend/                     # 后端（FastAPI）
│   ├── .env.example             # 配置模板
│   ├── requirements.txt         # Python 依赖
│   └── app/                     # 源码
└── frontend/                    # 前端（Next.js）
    ├── package.json             # Node 依赖
    └── app/                     # 页面源码
```

## 📖 文档

- [部署指南](./DEPLOY.md) — 环境要求、一键部署、手动部署、配置说明、常见问题

## 🔑 API Key 申请

真实模式需要以下 API Key（模拟模式不需要）：

| 服务 | 申请地址 | 用途 |
|------|---------|------|
| DeepSeek | https://platform.deepseek.com/ | 文本生成 |
| 阿里云百炼 | https://bailian.console.aliyun.com/ | 图像/视频/TTS |

## 📝 License

私有项目，未授权不可商用。
