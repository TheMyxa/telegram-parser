import json
import os
import shutil
from datetime import datetime
from pathlib import Path


def backup_problem_file(path):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.name}.bak_{timestamp}")
    shutil.copy2(path, backup_path)
    return backup_path


def load_json_dataset(path):
    dataset_path = Path(path)

    if not dataset_path.exists():
        return []

    try:
        with dataset_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        backup_path = backup_problem_file(dataset_path)
        print(f"Cannot read JSON dataset {dataset_path}: {e}. Backup saved to {backup_path}. Starting empty dataset.")
        return []

    if not isinstance(data, list):
        raise ValueError(f"Dataset must contain a JSON list: {dataset_path}")

    return data


def write_json_atomic(data, path, indent=2):
    target_path = Path(path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_name(f"{target_path.name}.tmp")

    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)

    os.replace(tmp_path, target_path)
