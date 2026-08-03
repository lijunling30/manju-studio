# AI 漫剧制作平台 · 技术栈需求说明书（PRD 附录 A）

> 版本：v1.2 ｜ 日期：2026-08-03 ｜ 作者：B 哥
> 定位：本文件独立成册，作为《AI 漫剧制作平台 PRD》的附录 A，供技术评审、架构设计、工时估算与采购报价直接使用。
> 配套文档：《AI漫剧平台-制作流程与技术选型方案.md》（流程侧）、《AI漫剧平台-PRD需求文档.md》（v1.3）
> v1.2 变更：对齐 PRD v1.3——新增人物子库（character_library）、确认闸口开关（bypassed 状态）、合规模块 M13（审核可选 + AI 标识强制）；分镜提示词纯中文（网关静默翻译）；更新验收标准与数据模型。

---

## 1. 架构总览（6 层）

```
L1 前端工作台         Next.js 14+ / Vue3+Nuxt · 剧本/分镜/时间线编辑器
        ↓ REST + WebSocket
L2 应用服务层         Python FastAPI · JWT/RBAC · 业务 CRUD
        ↓ 任务提交
L3 任务编排层         Celery + Redis → Temporal(DAG) · 断点续跑 · 重试
        ↓ 统一调用
L4 AI 模型网关        ★自建核心★ 多厂商路由 · 限流 · 重试 · 降级 · 成本记账
        ↓ HTTPS
L5 数据与存储         PostgreSQL+pgvector · Redis · OSS/COS · MinIO
L6 外部大模型 API     DeepSeek · 通义千问 · 豆包 · 可灵 · Vidu · Seedance · CosyVoice · SkyMusic · 内容安全
```

**架构决策原则**：
- 前后端分离，云端 SaaS 工作台形态，浏览器即用；
- 一切大模型调用必须经过 L4 网关（禁止业务代码直连厂商），这是平台的技术护城河；
- 视频生成类任务全部异步化（厂商接口本身是异步任务模式），由 L3 统一调度；
- 资产（图片/视频/音频）与元数据分离存储：对象存储放文件，PG 放结构化信息。

---

## 2. 分层技术选型明细表

### 2.1 L1 前端工作台

| 组件 | 主选 | 备选 | 版本要求 | 选型理由 |
|---|---|---|---|---|
| 框架 | Next.js | Vue 3 + Nuxt | Next 14+（App Router） | SSR/SEO、生态成熟、一体化 |
| UI 库 | Ant Design / shadcn/ui | Element Plus | 最新稳定版 | 后台工作台场景组件全 |
| 剧本编辑器 | Monaco Editor | CodeMirror 6 | 最新稳定版 | VS Code 同源，支持 JSON/大纲高亮 |
| 时间线/画布 | Konva.js | Fabric.js | 最新稳定版 | 分镜时间线、镜头拖拽编排 |
| 样式 | Tailwind CSS | CSS Modules | v3/v4 | 快速迭代 |
| 状态管理 | Zustand | Pinia | 最新 | 轻量、SSR 友好 |
| 实时进度 | WebSocket / SSE | 轮询兜底 | — | 任务进度推送 |
| 视频预览 | HTML5 + hls.js | — | — | 分片播放预览 |

### 2.2 L2 应用服务层

| 组件 | 主选 | 备选 | 版本要求 | 选型理由 |
|---|---|---|---|---|
| 语言/框架 | Python FastAPI | Node.js NestJS | Python 3.11+ | AI 生态友好、异步原生、自动 OpenAPI |
| API 文档 | FastAPI 内置 Swagger/OpenAPI | — | — | 前后端联调零成本 |
| 鉴权 | JWT + RBAC | OAuth2 | — | 多角色（创作者/管理员/B 端） |
| ORM | SQLAlchemy 2 + Alembic | Prisma（备） | 2.x | 迁移管理 |
| 校验 | Pydantic v2 | — | v2 | 与 FastAPI 原生契合 |
| 文件上传 | 直传 OSS（STS 临时凭证） | 服务端中转 | — | 大文件（视频）不经业务服务器 |

### 2.3 L3 任务编排层（异步任务核心）

| 组件 | 起步方案 | 进阶方案 | 说明 |
|---|---|---|---|
| 任务队列 | Celery + Redis | Temporal / Argo Workflows | 视频任务异步化必备 |
| 工作流 DAG | Celery Canvas（chain/group） | Temporal Workflow | 分镜→生图→生视频→配音→剪辑流水线 |
| 断点续跑 | 任务状态入库（PG） | Temporal 原生 | 失败任务从失败节点重试 |
| 任务状态机 | 自研（draft/confirmed/rejected/bypassed/queued/running/success/failed/retrying/manual_review） | — | 含确认闸口全链路状态（PRD 6.2） |
| 限流 | 网关层令牌桶 | — | 防止厂商配额打爆 |
| 优先级 | Redis 队列优先级 | — | 高优任务插队 |
| 确认闸口 | 任务提交前必经确认状态（draft→confirmed/bypassed） | — | 闸口开关与会话状态入库（PRD 5.0.1） |
| 合规检验任务 | 独立异步任务（审核报告入库） | — | 合规模块 M13，不影响主流水线 |

### 2.4 L4 AI 模型网关（★自建核心★）

| 能力 | 要求 | 说明 |
|---|---|---|
| 统一接口 | 一种请求格式适配所有厂商 | 屏蔽各家异步差异 |
| 厂商路由 | 按模型能力/价格/可用性自动路由 | 可灵/豆包/Vidu 切换 |
| 降级 | 主厂商失败自动切备选 | 视频任务单点依赖风险 |
| 重试 | 指数退避重试 | 网络/限流错误 |
| 限流 | 令牌桶 + 并发控制 | 保护配额与预算 |
| 异步任务管理 | 统一提交→轮询/回调→结果入库 | 视频 API 全是异步 |
| 成本记账 | 每次调用记录 token/时长/金额 | 按项目/用户出账单 |
| 确认闸口支撑 | 请求先经「意图复述 + 成本预估」确认，未确认不调用付费接口 | 确认前零计费（PRD 5.0.1/A-4） |
| 提示词翻译 | 中文提示词 → 厂商所需语言（后台静默翻译） | 用户界面全程中文，不暴露英文（PRD M4） |
| 密钥管理 | 加密存储各厂商 API Key | 不落前端、不落日志 |
| 监控 | 成功率/延迟/成本看板 | Prometheus + Grafana |
| 实现建议 | 自研（Go/Python）或 OneAPI/New API 二次开发 | 自研为长期护城河 |

### 2.5 L5 数据与资产存储

| 组件 | 主选 | 备选 | 用途 |
|---|---|---|---|
| 关系库 | PostgreSQL 15+ | — | 用户/项目/剧本/分镜/任务/账单 |
| 向量检索 | pgvector（PG 插件） | Milvus | 角色描述/分镜语义检索 |
| 缓存/队列 | Redis 7+ | — | 任务队列、缓存、限流计数 |
| 对象存储 | 阿里云 OSS / 腾讯 COS | MinIO（私有化） | 图片/视频/音频资产 |
| CDN | 云厂商 CDN | — | 成片分发、预览加速 |
| 资产版本 | 对象存储版本管理 | 自建 asset 版本表 | 抽卡候选、LoRA 版本 |

**核心数据表（与 PRD 7.1 对齐，v1.3）**：
| 表 | 关键字段 | 说明 |
|---|---|---|
| user | id, phone, role, plan, budget_limit, gate_setting | gate_setting=确认闸口偏好（会话/模块/全局） |
| project | id, name, genre, style_id, target_platform, status | — |
| novel | id, project_id, title, chapters[], characters[], settings | 小说 |
| script | id, novel_id, scenes[], emotion_curve | 剧本（JSON） |
| shot | id, script_id, shot_no, shot_type, camera_move, duration, prompt_zh, char_ref_ids, style_id, status | **纯中文提示词**（无 prompt_en） |
| character_library | id, user_id, name, desc, project_ids[], is_shared, status | **人物子库（M5）** |
| character | id, library_id, name, desc, ref_images[], expression_set[], lora_version | 角色挂子库 |
| keyframe | id, shot_id, image_url, score, is_approved | 抽卡候选 |
| video_task | id, shot_id, vendor, model, status, result_url, cost, retry_count | 异步任务 |
| audio_asset | id, shot_id, type(voice/bgm/sfx), asset_url, character_id | 音轨 |
| final_video | id, project_id, episode_no, url, platform_versions[], audit_status, cost_total | 成片 |
| cost_log | id, user_id, project_id, module, vendor, model, tokens/duration, amount, created_at | 成本 |
| ai_request | id, user_id, module, intent, params_json, cost_estimate, status(draft/confirmed/rejected/bypassed/timeout/cancelled), confirm_round, created_at, confirmed_at | **确认闸口（5.0.1）** |
| audit_report | id, final_video_id, vendor, status(pass/reject), issues[], report_url, created_at | **合规模块 M13 审核报告** |

### 2.6 L6 外部大模型 API（供应商对接清单）

| 环节 | 厂商/模型 | 接入方式 | 任务模式 | 计费维度 | 备注 |
|---|---|---|---|---|---|
| 小说/剧本/分镜 | DeepSeek-V3 | HTTP API | 同步 | token | 首选，成本低 |
| 结构化抽取 | 通义千问 qwen-plus/max（百炼） | HTTP + Function Calling | 同步 | token | JSON Schema |
| 角色生图 | 即梦 / 通义万相 | HTTP | 异步 | 张数/分辨率 | 资产入库 |
| 角色 LoRA | LiblibAI / 自建 SD | 平台训练 | 异步 | 训练次数 | P1/P2 |
| 视频生成 | Vidu Q3（一致性主力） | HTTP | **异步** | 时长/分辨率 | 漫剧首选 |
| 视频生成 | 豆包 Seedance 2.0 / 即梦 | HTTP | **异步** | 时长/分辨率 | 性价比批量 |
| 视频生成 | 可灵 Kling 2.0 | HTTP | **异步** | 时长/分辨率 | 精品画质 |
| TTS | 火山引擎豆包 TTS | HTTP | 异步 | 字符数 | 音色克隆 |
| 音乐 | 天工 SkyMusic / 网易天音 | HTTP | 异步 | 时长/条数 | BGM |
| 字幕 ASR | 阿里 Paraformer / 讯飞 | HTTP | 异步 | 音频时长 | 自动字幕 |
| 内容审核（M13 合规模块，用户可选） | 阿里云内容安全 / 腾讯云天御 | HTTP | 同步/异步 | 调用次数 | 用户自选启用；AI 生成标识为强制项（不由本模块控制） |

---

## 3. 部署与云资源需求（MVP 基线）

| 资源 | 规格建议 | 说明 |
|---|---|---|
| Web/API 服务器 | 4C8G × 2（容器化，弹性伸缩） | FastAPI + Next.js |
| 任务 Worker | 4C8G × 2（可扩至 4） | Celery Worker，视频任务长耗时 |
| PostgreSQL | 云 RDS 4C16G | 起步够用，pgvector 需装插件 |
| Redis | 云 Redis 4G | 队列/缓存 |
| 对象存储 | OSS/COS 标准存储 + CDN | 视频资产体积大 |
| 渲染节点（可选） | GPU 或纯 CPU FFmpeg | MVP 阶段 CPU 即可 |
| 部署方式 | Docker Compose → K8s | 先 Compose 快速上线，后迁 K8s |
| CI/CD | GitLab CI / GitHub Actions | 自动构建部署 |
| 监控 | Prometheus + Grafana + Sentry | 任务成功率/成本/错误 |

---

## 4. MVP 技术裁剪清单（明确不做 / 延后做）

| 项 | 状态 | 原因 |
|---|---|---|
| 角色 LoRA 训练 | P1 延后 | 复杂度高，先用参考图+首尾帧方案 |
| Temporal 完整 DAG | 起步用 Celery，流量大再迁 | 避免过度设计 |
| Milvus 独立向量库 | 起步用 pgvector | 数据量小 |
| 自研 SD 部署 | 直接调用厂商 API | 算力成本高 |
| 多租户复杂计费 | MVP 仅按项目记账 | 商业化后加 |
| 移动端 App | 只做 Web 响应式 | 工作台场景桌面优先 |

---

## 5. 技术验收标准（建议写入 PRD）

1. **一致性指标**：同一角色跨 20 个镜头，人脸相似度（可采样人工评审）通过率 ≥ 80%；
2. **抽卡效率**：单镜头平均生成 ≤ 3 次成功出合格关键帧（候选池 2-3 张）；
3. **任务可靠性**：视频生成任务成功率 ≥ 95%（含自动重试与降级），失败自动切备选厂商；
4. **成本控制**：单分钟成片 API 成本 ≤ 500 元（含重试与抽卡损耗）；每镜头成本可查询、可对账；
5. **端到端时效**：单集（60 镜头）全自动流水线 ≤ 24 小时；人工介入点 ≤ 3 处；
6. **合规分层**：所有导出成片强制携带 AI 生成标识（无开关，标识缺失禁止导出）；内容安全审核为用户可选模块（M13），启用时机器审核 + 人工复核，审核报告结构化入库；
7. **确认闸口**：所有 AI 调用先复述需求并经用户确认后才执行；闸口开关（会话/模块/全局）生效；未确认/超时不产生费用；高成本（≥50 元）或批量（≥20 镜头）任务即使关闭闸口仍强制确认；
8. **安全**：厂商 API Key 加密存储；任何密钥不落前端与日志；操作审计可追溯。

---

## 6. 待确认问题（影响技术选型）

1. 部署环境：公有云（阿里/腾讯）还是支持私有化交付？（影响 OSS/COS、K8s 选择）
2. 团队技术背景：后端偏 Python 还是 Node？（影响 FastAPI vs NestJS 定稿）
3. 视频厂商：是否接受「Vidu + 豆包」双主力？（影响网关路由设计）
4. 是否需要对外提供 OpenAPI 给第三方？（影响网关是否独立部署成产品）
5. 预算区间：月 API 消耗预估多少？（影响限流与成本记账策略）
6. 合规检验：公开分发场景是否默认强制开启内容审核（平台运营义务），仅内部预览/自用可跳过？（影响审核任务编排与报告存储，对应 PRD Q15）

> 以上 6 项确认后，技术栈可冻结，进入正式开发工时估算。
