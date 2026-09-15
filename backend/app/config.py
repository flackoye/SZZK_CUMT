from pathlib import Path
import torch

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
SAMPLE_DATA_DIR = BASE_DIR / "sample_data"
RUNTIME_DIR = BASE_DIR / "runtime"

# Ensure directories exist
MODELS_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_DATA_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL_ID = "v3-full"
DEFAULT_MODEL_PATH = MODELS_DIR / "V3-Full.pt"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".csv"}

# Sliding window hyperparameters
SEQ_WINDOW = 100
MIN_WINDOW = 200
WINDOW_SIZES = [25, 50, 100, 200]
BASE_FEATURE_NAMES = [
    "torque_mean", "torque_std", "torque_min", "torque_max", "torque_ptp", "torque_q25", "torque_q75", "torque_slope",
    "thrust_mean", "thrust_std", "thrust_min", "thrust_max", "thrust_ptp", "thrust_q25", "thrust_q75", "thrust_slope",
    "torque_thrust_corr", "torque_thrust_ratio", "depth_start", "depth_end"
]
MULTISCALE_FEATURE_NAMES = [f"w{size}_{name}" for size in WINDOW_SIZES for name in BASE_FEATURE_NAMES]

DAMAGE_CLASS_TO_LEVEL = {0: 0, 1: 20, 2: 40, 3: 60, 4: 80}
STRESS_CLASS_TO_MPA = {0: 0, 1: 10, 2: 20, 3: 30, 4: 40}
STATE_TO_LABEL = {
    d * 5 + s: f"D{DAMAGE_CLASS_TO_LEVEL[d]:02d}_S{STRESS_CLASS_TO_MPA[s]:02d}"
    for d in range(5) for s in range(5)
}

