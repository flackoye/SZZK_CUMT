"""Standalone CLI test script to verify V3-Full model inference on VTEST_S20.csv."""
from pathlib import Path
import sys
import time

import pandas as pd

from app.config import DEFAULT_MODEL_PATH, SAMPLE_DATA_DIR, DEVICE
from app.core.preprocessing import prepare_sliding_windows
from app.core.inference import load_model, run_model_inference
from app.core.metrics import compute_summary_metrics


def main():
    print(f"[{time.strftime('%H:%M:%S')}] 1. 检查运行环境与设备: {DEVICE}")

    model_path = DEFAULT_MODEL_PATH
    sample_csv = SAMPLE_DATA_DIR / "VTEST_S20.csv"

    if not model_path.exists():
        print(f"ERROR: 找不到权重文件 {model_path}")
        sys.exit(1)

    if not sample_csv.exists():
        print(f"ERROR: 找不到测试样本 {sample_csv}")
        sys.exit(1)

    print(f"[{time.strftime('%H:%M:%S')}] 2. 加载模型: {model_path.name}")
    t0 = time.time()
    model, checkpoint = load_model(model_path, DEVICE)
    print(f"  模型加载成功，耗时: {time.time() - t0:.2f}s")

    print(f"[{time.strftime('%H:%M:%S')}] 3. 读取并预处理数据: {sample_csv.name}")
    df_raw = pd.read_csv(sample_csv, encoding="utf-8-sig")
    print(f"  原始测点行数: {len(df_raw)}")

    t0 = time.time()
    seq_arr, phys_arr, meta_df = prepare_sliding_windows(df_raw)
    print(f"  特征矩阵计算成功，耗时: {time.time() - t0:.2f}s")
    print(f"  滑动窗口数: {len(seq_arr)} (预期: 7306)")
    print(f"  时序张量形状: {seq_arr.shape} (预期: [7306, 100, 3])")
    print(f"  物理特征形状: {phys_arr.shape} (预期: [7306, 80])")

    print(f"[{time.strftime('%H:%M:%S')}] 4. 执行 V3-Full 模型前向推理...")
    t0 = time.time()
    df_pred = run_model_inference(
        model=model,
        checkpoint=checkpoint,
        seq_arr=seq_arr,
        phys_arr=phys_arr,
        meta_df=meta_df,
        device=DEVICE,
    )
    print(f"  推理完成，耗时: {time.time() - t0:.2f}s")

    print(f"[{time.strftime('%H:%M:%S')}] 5. 评估反演指标:")
    metrics = compute_summary_metrics(df_pred)
    print(f"  窗口总数: {metrics['num_windows']}")
    print(f"  损伤分类准确率: {metrics['damage_accuracy'] * 100:.2f}%")
    print(f"  应力分类准确率: {metrics['stress_accuracy'] * 100:.2f}%")
    print(f"  状态分类准确率: {metrics['state_accuracy'] * 100:.2f}%")
    print(f"  状态宏 F1:     {metrics['macro_f1'] * 100:.2f}%")
    print(f"  平均置信度:     {metrics['mean_confidence'] * 100:.2f}%")

    assert metrics["num_windows"] == 7306, f"窗口数应为 7306，实际为 {metrics['num_windows']}"
    assert metrics["damage_accuracy"] > 0.70, f"损伤准确率异常: {metrics['damage_accuracy']}"
    assert metrics["stress_accuracy"] > 0.70, f"应力准确率异常: {metrics['stress_accuracy']}"

    print("\n[SUCCESS] 验证全部通过！核心链路完全正确且稳定。")


if __name__ == "__main__":
    main()
