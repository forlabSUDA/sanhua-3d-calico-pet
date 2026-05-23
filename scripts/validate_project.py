from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "pet-package" / "sanhua-3d-calico-motionfix"
QA = ROOT / "qa"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def main() -> None:
    pet_json = PACKAGE / "pet.json"
    spritesheet = PACKAGE / "spritesheet.webp"
    if not pet_json.exists():
        fail(f"missing {pet_json}")
    if not spritesheet.exists():
        fail(f"missing {spritesheet}")

    data = json.loads(pet_json.read_text(encoding="utf-8-sig"))
    image = Image.open(spritesheet)

    if image.size != (1536, 1872):
        fail(f"spritesheet size is {image.size}, expected (1536, 1872)")
    if data.get("grid") != {"columns": 8, "rows": 9}:
        fail(f"grid is {data.get('grid')}, expected 8x9")
    if data.get("frameSize") != {"width": 192, "height": 208}:
        fail(f"frameSize is {data.get('frameSize')}, expected 192x208")

    states = [state.get("name") for state in data.get("states", [])]
    expected = [
        "idle",
        "running-right",
        "running-left",
        "waving",
        "jumping",
        "failed",
        "waiting",
        "running",
        "review",
    ]
    if states != expected:
        fail(f"states are {states}, expected {expected}")

    for name in ["validation.json", "frame_stability_report.json", "review.json", "run.log"]:
        if not (QA / name).exists():
            fail(f"missing qa/{name}")

    validation = json.loads((QA / "validation.json").read_text(encoding="utf-8"))
    if validation.get("ok") is not True:
        fail(f"qa/validation.json is not ok: {validation}")

    print("OK: project package is valid")
    print(f"pet id: {data.get('id')}")
    print(f"display name: {data.get('displayName')}")
    print(f"spritesheet: {spritesheet}")


if __name__ == "__main__":
    main()
