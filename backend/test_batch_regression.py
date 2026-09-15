import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.services.job_service import job_service, CANONICAL_ORDER_MAP
from app.services.model_service import model_service
import time

def test_batch_execution():
    print("Initializing model...")
    ok = model_service.initialize()
    assert ok and model_service.is_ready, "Model failed to initialize"
    print("Model initialized successfully!")
    golden_dir = backend_dir.parent / "qianduan" / "public" / "data" / "golden_batch"
    csv_files = sorted(list(golden_dir.glob("*.csv")))
    print(f"Found {len(csv_files)} CSV files in {golden_dir}")
    assert len(csv_files) == 11, f"Expected 11 CSV files, found {len(csv_files)}"

    # Prepare file items
    file_items = []
    for f in csv_files:
        file_items.append((f.name, f.read_bytes()))

    print("Creating batch job...")
    job = job_service.create_job(file_items)
    print(f"Created job: {job.run_id}, status: {job.status}")

    # Wait for completion
    start_t = time.time()
    while job.status in ("queued", "running"):
        time.sleep(0.5)
        print(f"Progress: {job.progress}% [{job.stage}] - {job.message}")
        if time.time() - start_t > 120:
            raise TimeoutError("Batch job timed out after 120s")

    print(f"Final status: {job.status}, completed_at: {job.completed_at}")
    if job.status == "failed":
        print(f"Error: {job.error}")
        sys.exit(1)

    # Validate result payload
    payload = job.result_payload
    assert payload is not None, "Payload is None"
    assert "files" in payload, "Missing 'files' in payload"
    assert len(payload["files"]) == 11, f"Expected 11 files in payload, got {len(payload['files'])}"
    print(f"Verified 11 files in payload: {[f['file_name'] for f in payload['files']]}")

    # Validate spatial roadway
    spatial = payload.get("spatialRoadway")
    assert spatial is not None, "Missing spatialRoadway"
    sec_b = next((g for g in spatial["groups"] if g["id"] == "B"), None)
    assert sec_b is not None, "Section B not found in spatialRoadway"
    
    current_run_holes = [h for h in sec_b["boreholes"] if h.get("isCurrentRun")]
    print(f"Section B updated boreholes count: {len(current_run_holes)}")
    assert len(current_run_holes) == 11, f"Expected all 11 boreholes in Section B to have isCurrentRun=True, got {len(current_run_holes)}"

    # Validate predictions.csv
    pred_csv = job.work_dir / "predictions.csv"
    assert pred_csv.exists(), "predictions.csv not created"
    print(f"Combined predictions.csv exists, size: {pred_csv.stat().st_size} bytes")

    print("ALL BATCH REGRESSION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_batch_execution()
