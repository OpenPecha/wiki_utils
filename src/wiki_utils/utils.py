import json
from pathlib import Path


def write_json(data: dict | list, output_path: str | Path):
    with open(output_path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(file_path: str | Path):
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    return data
