# SZIC 随钻智控模型推理服务后端 (Backend)

基于 FastAPI + PyTorch 构建的随钻参数多尺度特征提取与围岩状态物理融合推理服务。

## 目录架构

```text
backend/
├── app/
│   ├── api/
│   │   ├── health.py         # GET /health 健康检查与模型就绪检测
│   │   └── runs.py           # POST /runs 任务创建、GET /runs/{id} 状态查询、GET /runs/{id}/result 结果获取
│   ├── core/
│   │   ├── model.py          # V3-Full (FullModelStandard) PyTorch 模型架构
│   │   ├── preprocessing.py  # 4 尺度 (25/50/100/200) 80 维滚动物理特征计算与窗口切分
│   │   ├── inference.py      # 模型标准化与批处理前向推理
│   │   └── metrics.py        # 准确率、宏 F1 与混淆统计
│   ├── services/
│   │   ├── model_service.py  # 单例模型加载与生命周期管理
│   │   ├── job_service.py    # 异步推理任务编排与进度汇报
│   │   └── result_adapter.py # 前端看板 JSON 格式适配器
│   ├── config.py             # 服务配置与路径常量
│   ├── schemas.py            # Pydantic 数据契约
│   └── main.py               # FastAPI 应用入口与 CORS
├── models/
│   └── V3-Full.pt            # V3-Full 经核验的训练权重与 Scaler
├── sample_data/
│   └── VTEST_S20.csv         # 黄金测试样例 (7505 行)
├── runtime/                  # 每次任务的隔离输出与执行日志 (gitignore)
├── requirements.txt          # Python 依赖清单
├── backend.ps1               # 后端一键设置与运行脚本
└── test_cli.py               # 核心链路独立离线校验脚本
```

## 快速运行

在 `backend` 目录下：

```powershell
# 1. 初始化虚拟环境并安装依赖
.\backend.ps1 setup

# 2. 独立验证模型推理核心链路
.\backend.ps1 test

# 3. 启动本地 API 服务 (127.0.0.1:8000)
.\backend.ps1 dev
```

服务就绪后，访问 http://127.0.0.1:8000/docs 可直接查看交互式 Swagger API 文档。

