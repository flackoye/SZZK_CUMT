# 本地开发工作区
# SZIC 随钻智控平台 本地工作区
# SZIC 随钻智控平台 (Smart Zone Intelligence Control)

根目录的 Git 仓库统一管理前端及后续后端代码，主分支为 main。
根目录统一管理 Vue 3 前端与 FastAPI Python 后端服务，主分支为 main。
基于随钻参数与深度学习驱动的矿山围岩动力学灾害（冲击地压/顶板冒落）智能预警与决策平台。
本工作区包含 Vue 3 前端大屏可视化系统与基于 FastAPI + PyTorch 的 V3-Full 物理融合深度学习推理后端。

## 前端来源
---

上游：https://github.com/DanoAndHolidays/Mine.git
核对提交：bf7bf6ffe711a37c3083eeeaa234909299434d8c
完整上游克隆保存在 .local-tools/upstream（含原始 Git 历史，已忽略）。
现有 qianduan/src 与该提交一致；保留本地额外数据和工具文件。
根目录不设置指向前端仓库的 push remote，避免将整个工作区误推到前端仓库。
## 快速启动（协同运行）
## 快速启动

## 运行
遵循 **“先后端、后前端”** 原则：
系统启动遵循 **“先后端 (127.0.0.1:8000)，后前端 (127.0.0.1:5173)”** 原则。

在根目录 PowerShell 中执行：
### 方式 A：一键协同启动（推荐）
### 首次使用准备（安装依赖）

在根目录 PowerShell 执行：
在根目录打开 PowerShell 终端，执行依赖安装：

```powershell
# 1. 安装前端 Node 依赖（基于锁定版本的 pnpm）
./frontend.ps1 install
./frontend.ps1 dev
./start.ps1
```

访问 http://127.0.0.1:5173，按 Ctrl+C 停止。
生产构建：`./frontend.ps1 build`；预览：`./frontend.ps1 preview`（端口 4173）。
脚本优先使用已有 Node/pnpm，否则使用本机 Codex 已提供的运行时，不修改 PATH。
本次验证环境：Node 24.19.0、pnpm 11.19.0；使用 pnpm-lock.yaml 锁定依赖。
package-lock.json 为上游原文件，保留用于溯源，本工作区统一使用 pnpm。
依赖位于 qianduan/node_modules，缓存位于 .pnpm-store，构建位于 qianduan/dist。
端口被占用会明确报错，不会停止其他进程或自动切换端口。
该脚本将依次：
1. 检查并初始化后端 Python 虚拟环境与依赖；
2. 启动 Python 后端服务并循环检查健康状态 (`http://127.0.0.1:8000/health`)；
3. 后端与 V3-Full 模型就绪后，自动启动 Vue 前端大屏 (`http://127.0.0.1:5173`)。
> **提示**：后端 Python 依赖和虚拟环境将在首次运行启动脚本时自动检测并初始化（位于 `backend/.venv`），无需手动处理。

## 后端开发
---

后续后端代码可放在根目录 backend/，Python 依赖使用该目录的 .venv。
前端当前以 public/data 和 public/models 的静态资源运行，不需要后端即可启动。
接入后端时将 qianduan/.env.example 复制为 qianduan/.env.local，启用并设置两个变量，然后重启：
### 方式 B：双终端独立启动
### 方式 A：一键协同启动（推荐）

```dotenv
VITE_APP_BASE_API=/api
VITE_HOST_URL=http://127.0.0.1:8000
#### 1. 启动后端 (127.0.0.1:8000)
在根目录 PowerShell 执行协同启动脚本：

打开第一个 PowerShell 终端：

```powershell
cd backend
.\backend.ps1 dev
./start.ps1
```

代理会将 /api 前缀去除，例如 /api/health 转发为后端 /health。
该配置只提供开发代理，业务 API 调用仍需在后续开发中实现。
.env.local 不纳入 Git；不要在 VITE_ 变量中放秘密信息。
- API 基础地址：`http://127.0.0.1:8000`
- 交互式 Swagger 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`
- 独立算法测试：`.\backend.ps1 test`
**执行流程**：
1. 自动检查并就绪后端 Python 虚拟环境与 PyTorch 算法环境；
2. 在新窗口启动 FastAPI 后端服务 (`http://127.0.0.1:8000`)；
3. 循环发起健康检查探针 (`/health`)，直到后端算法引擎与模型权重完全就绪；
4. 启动前端 Vite 开发服务器 (`http://127.0.0.1:5173`) 并自动在默认浏览器中打开。

## 隔离与版本管理
#### 2. 启动前端 (127.0.0.1:5173)
---

未安装全局包，未修改系统 PATH 或全局 Git 配置。
.local-tools 中保留上游克隆、初始空 Git 元数据备份及本次收回的缓存。
首次提交使用 Codex Local Setup <codex@local.invalid> 标记自动初始化；后续请按需要设置仓库级提交身份。
生产构建通过；原有 Sass legacy-js-api 与 @import 弃用提示暂保留。
打开第二个 PowerShell 终端：
### 方式 B：双终端独立启动（调试备用）

如需分别调试前后端输出，可在两个独立的 PowerShell 终端中分别启动：

#### 终端 1：启动 Python 后端
```powershell
cd backend
.\backend.ps1 dev
```
- 服务地址：`http://127.0.0.1:8000`
- 交互式 Swagger API 文档：`http://127.0.0.1:8000/docs`
- 算法引擎健康状态：`http://127.0.0.1:8000/health`
- 独立算法测试套件：`.\backend.ps1 test`

#### 终端 2：启动 Vue 前端
```powershell
./frontend.ps1 dev
```
- 前端大屏访问地址：`http://127.0.0.1:5173`
- 前端已通过 `qianduan/.env.local` 将 `/api/*` 请求透明代理至 `http://127.0.0.1:8000/*`，避免浏览器跨域并统一调用路由。

访问 `http://127.0.0.1:5173`。

---

## 端到端真实推理工作流

1. 浏览器打开大屏，点击右上角 **“导入数据”** 按钮；
2. 拖拽或选择实际钻进 CSV 文件（或点击“载入黄金样例数据”载入 `VTEST_S20.csv`）；
3. 点击 **“开始导入”**：
   - 前端真实调用后端 `POST /runs` 创建任务；
   - 界面同步展示：`数据校验` -> `多尺度特征计算` -> `V3-Full 物理融合推理` -> `结果适配` 各阶段实时进度；
   - 任务完成后，后端返回预测序列与汇总指标，自动注入 Pinia Store 并动态驱动：
     - **右侧 04 面板**：模型损伤准确率、应力准确率、宏 F1 环形仪表盘；
     - **左侧 02/03 面板**：真实扭矩/推力钻进趋势曲线与 KPI；
     - **中央舞台与底部**：当前钻孔时空点位与三维围岩双场联动更新；
     - **顶部状态栏**：显示 `真实推理已生效 (RUN: <run_id>)`。
1. **服务健康检测**：
   - 前端顶部状态栏实时显示后端连接状态（若后端未就绪，导入按钮会自动锁定并提示重试）。
2. **导入随钻数据**：
   - 点击右上角 **“导入数据”** 按钮；
   - 拖拽或选取现场随钻 CSV 文件（小于 50MB），亦可点击 **“载入黄金样例数据”** 直接装载标准测井数据（`VTEST_S20.csv`）。
3. **真实推理与结果驱动**：
   - 点击 **“开始导入”**，前端发起 `POST /runs` 异步任务并执行非重叠轮询；
   - 任务完成后，自动加载真实推理结果，驱动全平台视图更新：
     - **中央三维空间围岩场 (RockCloud3D)**：基于实测推断重构巷道钻孔的应力场与损伤场点云；
     - **左侧钻进曲线 (Panel 02/03)**：展示当前钻孔真实推力、扭矩等全生命周期时序与统计 KPI；
     - **右侧模型指标 (Panel 04/05)**：若数据包含实测真实标签，显示当前任务实际计算的准确率与宏 F1；若无标签则客观展示 `N/A`，并与基准历史模型隔离对比；
     - **页面无缝下钻**：支持平滑进入 “卸压决策” 详图与返回大屏，无报错与内存泄漏。

---

## 端口与代理配置
## 常用脚本一览

- 前端开发服务器：`http://127.0.0.1:5173`
- 后端 API 服务器：`http://127.0.0.1:8000`
- 前端通过 `qianduan/.env.local` 将 `/api/*` 反向代理至 `http://127.0.0.1:8000/*`，避免跨域并统一接口路径。
| 脚本命令 | 说明 |
| :--- | :--- |
| `./start.ps1` | 一键协同启动后端健康检查与前端服务（主推） |
| `./frontend.ps1 install` | 安装前端 pnpm 锁定依赖 |
| `./frontend.ps1 dev` | 独立运行前端开发服务 (端口 5173) |
| `./frontend.ps1 build` | 编译前端生产静态文件 (`qianduan/dist`) |
| `./frontend.ps1 preview` | 预览前端生产构建 (端口 4173) |
| `cd backend; .\backend.ps1 dev` | 独立运行后端 FastAPI 服务 (端口 8000) |
| `cd backend; .\backend.ps1 test` | 运行后端推理 CLI 离线回归测试 |

---

## 架构与技术栈

- **前端 (qianduan/)**: Vue 3 + Vite + Pinia + Three.js + ECharts + SCSS
- **后端 (backend/)**: Python 3.10+ + FastAPI + Uvicorn + Pydantic v2
- **算法模型**: V3-Full Physics-Guided Neural Network (多尺度时空特征提取 + 围岩动力学物理守恒约束)
