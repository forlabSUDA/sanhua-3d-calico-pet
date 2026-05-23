from __future__ import annotations

import json
import math
import shutil
import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage


WORKSPACE = Path(__file__).resolve().parents[1]

# Project-local layout. This copy is meant to run after cloning/downloading
# this repository, so it uses source_frames/ as input and build/ as output.
SOURCE_FRAMES = WORKSPACE / "source_frames"
OUT = WORKSPACE / "build" / "sanhua_3d_pet_motionfix_all"

MASTER_DIR = OUT / "master_frames"
CODEX_DIR = OUT / "codex_frames"
QA_DIR = OUT / "qa"
PREVIEW_DIR = QA_DIR / "previews"
DIFF_DIR = QA_DIR / "motion_diff"
FINAL_DIR = OUT / "final"

CELL_W = 192
CELL_H = 208
COLS = 8
ROWS = 9
GROUND_Y = CELL_H - 8

PET_ID = "sanhua-3d-calico-motionfix"
DISPLAY_NAME = "三花猫猫 3D 修复版"
DESCRIPTION = "A repaired realistic 3D calico cat desktop pet with stabilized motion and full-body failed/jumping frames."

ROW_DEFS: list[tuple[str, int]] = [
    ("idle", 6),
    ("running-right", 8),
    ("running-left", 8),
    ("waving", 4),
    ("jumping", 5),
    ("failed", 8),
    ("waiting", 6),
    ("running", 6),
    ("review", 6),
]

MASTER_COUNTS = {
    "idle": 16,
    "running-right": 32,
    "running-left": 32,
    "waving": 16,
    "jumping": 24,
    "failed": 24,
    "waiting": 24,
    "running": 16,
    "review": 16,
}

FRAME_DURATIONS = {
    "idle": [280, 110, 110, 140, 140, 360],
    "running-right": [92, 98, 92, 98, 92, 98, 92, 160],
    "running-left": [92, 98, 92, 98, 92, 98, 92, 160],
    "waving": [130, 120, 140, 320],
    "jumping": [140, 110, 130, 150, 310],
    "failed": [120, 140, 170, 150, 180, 140, 140, 320],
    "waiting": [210, 150, 230, 130, 330, 360],
    "running": [150, 120, 130, 120, 150, 320],
    "review": [170, 150, 160, 150, 180, 340],
}

STATE_SEMANTICS = {
    "idle": "breathing, tiny blink, ear and tail micro-motion",
    "running-right": "right-facing gait with controlled 2.5D legs and tail",
    "running-left": "left-facing mirrored gait with controlled 2.5D legs and tail",
    "waving": "small paw response",
    "jumping": "crouch, takeoff, peak, fall, land",
    "failed": "side-lying relaxed roll / belly-up motion",
    "waiting": "stretch plus wide-mouth yawn",
    "running": "focused working micro-motion, not directional travel",
    "review": "look, head tilt, quiet observation",
}

GLOBAL_VISUAL_TARGET_AREA = 11200
ROW_SCALE_MIN = 0.74
ROW_SCALE_MAX = 1.08


@dataclass
class RowResult:
    name: str
    keyframes: list[Image.Image]
    master: list[Image.Image]
    codex: list[Image.Image]
    scale: float
    pipeline: str
    repaired: bool
    failures_before_repair: list[str]
    remaining_visual_problems: list[str]


def ensure_dirs() -> None:
    for path in [MASTER_DIR, CODEX_DIR, QA_DIR, PREVIEW_DIR, DIFF_DIR, FINAL_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def clean_output() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    ensure_dirs()


def normalize_alpha(image: Image.Image) -> Image.Image:
    arr = np.array(image.convert("RGBA"))
    arr[arr[:, :, 3] < 6, 3] = 0
    arr[arr[:, :, 3] == 0, :3] = 0
    return Image.fromarray(arr, "RGBA")


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    return image.convert("RGBA").getchannel("A").getbbox()


def trim_alpha(image: Image.Image, pad: int = 8) -> Image.Image:
    bbox = alpha_bbox(image)
    if not bbox:
        return image.convert("RGBA")
    return image.crop(
        (
            max(0, bbox[0] - pad),
            max(0, bbox[1] - pad),
            min(image.width, bbox[2] + pad),
            min(image.height, bbox[3] + pad),
        )
    ).convert("RGBA")


def keep_primary_components(image: Image.Image, min_area: int = 24) -> Image.Image:
    arr = np.array(image.convert("RGBA"))
    alpha = arr[:, :, 3]
    mask = alpha > 8
    labels, count = ndimage.label(mask)
    if count <= 1:
        return normalize_alpha(image)
    areas = ndimage.sum(mask, labels, index=np.arange(1, count + 1))
    if len(areas) == 0:
        return normalize_alpha(image)
    main = int(np.argmax(areas)) + 1
    keep = labels == main
    grown = ndimage.binary_dilation(keep, iterations=5)
    for label, area in enumerate(areas, start=1):
        if label == main or area < min_area:
            continue
        component = labels == label
        if np.any(component & grown):
            keep |= component
    arr[:, :, 3] = np.where(keep, alpha, 0).astype(np.uint8)
    return normalize_alpha(Image.fromarray(arr, "RGBA"))


def load_source_frames(row_name: str) -> list[Image.Image]:
    row_dir = SOURCE_FRAMES / row_name
    frames = [Image.open(path).convert("RGBA") for path in sorted(row_dir.glob("*.png"))]
    if not frames:
        raise FileNotFoundError(f"Missing source frames for {row_name}: {row_dir}")
    return [keep_primary_components(normalize_alpha(frame)) for frame in frames]


def checker(size: tuple[int, int], block: int = 8) -> Image.Image:
    im = Image.new("RGB", size, (242, 242, 242))
    draw = ImageDraw.Draw(im)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle((x, y, x + block - 1, y + block - 1), fill=(222, 222, 222))
    return im


def shift_image(image: Image.Image, dx: int = 0, dy: int = 0) -> Image.Image:
    out = Image.new("RGBA", image.size, (0, 0, 0, 0))
    out.alpha_composite(image.convert("RGBA"), (dx, dy))
    return normalize_alpha(out)


def solidify_visible_pixels(image: Image.Image, min_alpha: int = 165) -> Image.Image:
    arr = np.array(image.convert("RGBA"))
    visible = arr[:, :, 3] > 12
    arr[visible, 3] = np.maximum(arr[visible, 3], min_alpha)
    arr[arr[:, :, 3] == 0, :3] = 0
    return Image.fromarray(arr, "RGBA")


def fixed_size_pose(image: Image.Image, target_w: int, target_h: int, baseline_y: int = GROUND_Y) -> Image.Image:
    crop = trim_alpha(keep_primary_components(image), 4)
    bbox = alpha_bbox(crop)
    if not bbox:
        return Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
    resized = crop.resize((target_w, target_h), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
    x = round((CELL_W - target_w) / 2)
    y = round(baseline_y - target_h)
    out.alpha_composite(resized, (x, y))
    return normalize_alpha(out)


def sharpen_rgba(image: Image.Image, percent: int = 85) -> Image.Image:
    rgba = normalize_alpha(image)
    alpha = rgba.getchannel("A")
    rgb = rgba.convert("RGB").filter(ImageFilter.UnsharpMask(radius=0.7, percent=percent, threshold=2))
    out = Image.merge("RGBA", (*rgb.split(), alpha))
    return normalize_alpha(out)


def fit_pose_preserve_aspect(
    image: Image.Image,
    max_w: int,
    max_h: int,
    baseline_y: int = GROUND_Y,
    center_x: int = CELL_W // 2,
    upscale_limit: float = 1.08,
) -> Image.Image:
    """Place one pose in a cell without distorting its face/body proportions."""
    crop = trim_alpha(keep_primary_components(image), 4)
    bbox = alpha_bbox(crop)
    if not bbox:
        return Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
    ratio = min(max_w / max(1, crop.width), max_h / max(1, crop.height), upscale_limit)
    size = (max(1, round(crop.width * ratio)), max(1, round(crop.height * ratio)))
    resized = crop.resize(size, Image.Resampling.LANCZOS)
    resized = sharpen_rgba(resized, 75)
    rb = alpha_bbox(resized)
    out = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
    if rb:
        x = round(center_x - (rb[0] + rb[2]) / 2)
        y = round(baseline_y - rb[3])
        x = max(0, min(CELL_W - resized.width, x))
        y = max(0, min(CELL_H - resized.height, y))
        out.alpha_composite(resized, (x, y))
    return normalize_alpha(out)


def paste_masked_region(source: Image.Image, mask: np.ndarray) -> Image.Image:
    arr = np.array(source.convert("RGBA"))
    out = np.zeros_like(arr)
    out[mask] = arr[mask]
    return normalize_alpha(Image.fromarray(out, "RGBA"))


def bbox_from_mask(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def center_of_bbox(bbox: tuple[int, int, int, int] | None) -> tuple[float, float]:
    if not bbox:
        return (CELL_W / 2, CELL_H / 2)
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


def body_leg_tail_masks(frame: Image.Image) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    arr = np.array(frame.convert("RGBA"))
    alpha = arr[:, :, 3] > 8
    bbox = alpha_bbox(frame)
    if not bbox:
        empty = np.zeros(alpha.shape, dtype=bool)
        return empty, empty, empty
    left, top, right, bottom = bbox
    w = max(1, right - left)
    h = max(1, bottom - top)
    yy, xx = np.indices(alpha.shape)
    rx = (xx - left) / w
    ry = (yy - top) / h

    tail = alpha & (rx < 0.29) & (ry > 0.18) & (ry < 0.88)
    leg_zone = alpha & (ry > 0.50) & (rx > 0.18) & (rx < 0.98)
    body = alpha & ~tail & ~leg_zone
    # Keep the lower belly, but remove most dangling leg pixels from the body plate.
    belly = alpha & (ry > 0.47) & (ry < 0.68) & (rx > 0.28) & (rx < 0.78)
    body |= belly
    leg_zone &= ~belly
    return body, leg_zone, tail


def compose_running_keyposes(right_frames: list[Image.Image]) -> list[Image.Image]:
    """Use clear rendered gait keys and preserve proportions.

    The previous puppet pass split the already-small 192px cat into body/legs
    and then forced it into a target rectangle. That made the face deform and
    the legs turn into pale fragments. This pass keeps the original rendered
    full-body key poses, only doing proportional fit and row-level placement.
    """
    keyposes: list[Image.Image] = []
    for phase, frame in enumerate(right_frames[:8]):
        bob = -1 if phase in {1, 5} else 0
        keyposes.append(fit_pose_preserve_aspect(frame, 186, 126, GROUND_Y + bob, upscale_limit=1.08))
    return keyposes


def compose_jumping_keyposes(source: list[Image.Image]) -> list[Image.Image]:
    # Clear Codex semantics: crouch -> takeoff -> peak -> fall -> land.
    # Keep each rendered pose proportional. Do not reuse and stretch one frame.
    crouch = source[0]
    takeoff = source[1 if len(source) > 1 else 0]
    peak = source[2 if len(source) > 2 else 1 if len(source) > 1 else 0]
    fall = source[3 if len(source) > 3 else 1 if len(source) > 1 else 0]
    land = source[4 if len(source) > 4 else 0]
    return [
        fit_pose_preserve_aspect(crouch, 184, 130, CELL_H - 8),
        fit_pose_preserve_aspect(takeoff, 184, 158, CELL_H - 28),
        fit_pose_preserve_aspect(peak, 184, 126, CELL_H - 70),
        fit_pose_preserve_aspect(fall, 184, 142, CELL_H - 32),
        fit_pose_preserve_aspect(land, 184, 158, CELL_H - 8),
    ]


def make_jumping_master(keyframes: list[Image.Image]) -> list[Image.Image]:
    # 24 frames, preserving the five logical poses without morphing them into
    # unrelated cats. Motion is carried by vertical placement and holds.
    sequence = [0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 4, 0, 0]
    return [keyframes[idx].copy() for idx in sequence]


def compose_failed_keyposes(source: list[Image.Image]) -> list[Image.Image]:
    # Avoid the jump from a huge upright sit directly into a small lying pose.
    # Frames 03/04/06/07 in the original failed row are very flat side strips;
    # at pet size they read like half a cat. Keep the full slumped sit, the
    # full-body sink, and the readable belly-up roll pose instead.
    indices = [0, 1, 2, 2, 5, 5, 5, 5]
    poses = [source[min(i, len(source) - 1)] for i in indices]
    return poses


def make_running_master(keyposes: list[Image.Image]) -> list[Image.Image]:
    # Four frames per phase, no optical flow or crossfade. The Codex row uses
    # the eight clear gait poses; this master only adds tiny whole-body bobbing
    # so the high-FPS preview does not introduce soft leg ghosts.
    master: list[Image.Image] = []
    for phase, current in enumerate(keyposes):
        for sub in range(4):
            f = sub / 4
            bob = round(math.sin(((phase + f) / 8) * 2 * math.pi) * 1.25)
            master.append(shift_image(current, 0, bob))
    return master[:32]


def mirror_frames(frames: list[Image.Image]) -> list[Image.Image]:
    return [frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT) for frame in frames]


def row_normalize_frames(
    frames: list[Image.Image],
    row_name: str,
    allow_vertical_motion: bool = False,
    target_fill: float | None = None,
) -> tuple[list[Image.Image], float]:
    cleaned = [trim_alpha(keep_primary_components(frame), 7) for frame in frames]
    bboxes = [alpha_bbox(frame) for frame in cleaned]
    valid = [bbox for bbox in bboxes if bbox]
    if not valid:
        return [Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0)) for _ in frames], 1.0
    max_w = max(b[2] - b[0] for b in valid)
    max_h = max(b[3] - b[1] for b in valid)
    limit_w = CELL_W - 8 if row_name in {"running-right", "running-left", "failed", "waiting"} else CELL_W - 14
    limit_h = CELL_H - 10 if row_name in {"failed", "waiting"} else CELL_H - 14
    scale = min(limit_w / max(1, max_w), limit_h / max(1, max_h), 1.08)
    if target_fill is not None:
        scale = min(scale, target_fill)

    centers = []
    bottoms = []
    for bbox in valid:
        centers.append((bbox[0] + bbox[2]) / 2)
        bottoms.append(bbox[3])
    anchor_x = float(np.median(centers))
    source_baseline = float(np.median(bottoms))
    ground_y = CELL_H - 8
    if row_name == "jumping":
        ground_y = CELL_H - 12

    out_frames: list[Image.Image] = []
    for frame, bbox in zip(cleaned, bboxes):
        if not bbox:
            out_frames.append(Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0)))
            continue
        scaled_size = (
            max(1, round(frame.width * scale)),
            max(1, round(frame.height * scale)),
        )
        scaled = frame.resize(scaled_size, Image.Resampling.LANCZOS)
        scaled_bbox = alpha_bbox(scaled)
        cell = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
        if scaled_bbox:
            frame_anchor = ((bbox[0] + bbox[2]) / 2) * scale
            x = round(CELL_W / 2 - frame_anchor)
            if allow_vertical_motion:
                delta_bottom = (bbox[3] - source_baseline) * scale
                y = round(ground_y - scaled_bbox[3] - delta_bottom)
            else:
                y = round(ground_y - scaled_bbox[3])
            y = max(0, min(CELL_H - scaled.height, y))
            cell.alpha_composite(scaled, (x, y))
        out_frames.append(normalize_alpha(cell))
    return out_frames, scale


def row_metrics_for_audit(frames: list[Image.Image], row_name: str, scale_factor: float) -> list[dict]:
    records: list[dict] = []
    for idx, frame in enumerate(frames):
        bbox = alpha_bbox(frame)
        if not bbox:
            records.append(
                {
                    "row_name": row_name,
                    "frame_index": idx,
                    "bbox_width": 0,
                    "bbox_height": 0,
                    "alpha_area": 0,
                    "center_x": 0,
                    "center_y": 0,
                    "baseline_y": 0,
                    "margins": json.dumps({"left": 0, "top": 0, "right": 0, "bottom": 0}, ensure_ascii=False),
                    "scale_factor": scale_factor,
                }
            )
            continue
        left, top, right, bottom = bbox
        alpha = np.array(frame.getchannel("A"))
        margins = {"left": left, "top": top, "right": CELL_W - right, "bottom": CELL_H - bottom}
        records.append(
            {
                "row_name": row_name,
                "frame_index": idx,
                "bbox_width": right - left,
                "bbox_height": bottom - top,
                "alpha_area": int((alpha > 8).sum()),
                "center_x": round((left + right) / 2, 3),
                "center_y": round((top + bottom) / 2, 3),
                "baseline_y": bottom,
                "margins": json.dumps(margins, ensure_ascii=False),
                "scale_factor": round(scale_factor, 6),
            }
        )
    return records


def write_audit_csv(path: Path, records: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "row_name",
        "frame_index",
        "bbox_width",
        "bbox_height",
        "alpha_area",
        "center_x",
        "center_y",
        "baseline_y",
        "margins",
        "scale_factor",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    return str(path)


def median_area(frames: list[Image.Image]) -> float:
    values = []
    for frame in frames:
        alpha = np.array(frame.getchannel("A"))
        values.append(int((alpha > 8).sum()))
    return float(np.median(values)) if values else 0.0


def row_safe_upscale(frames: list[Image.Image], allow_vertical_motion: bool) -> float:
    safe = ROW_SCALE_MAX
    for frame in frames:
        bbox = alpha_bbox(frame)
        if not bbox:
            continue
        left, top, right, bottom = bbox
        cx = (left + right) / 2
        width = max(1, right - left)
        height = max(1, bottom - top)
        # Keep a 3 px anatomical margin after row-level scaling.
        safe_w = (CELL_W - 6) / width
        safe_h = (CELL_H - 6) / height
        safe = min(safe, safe_w, safe_h)
        if not allow_vertical_motion:
            safe = min(safe, (CELL_H - 6) / height)
    return max(0.1, safe)


def make_scale_adjustment_plan(results: dict[str, RowResult]) -> tuple[dict[str, float], list[dict]]:
    factors: dict[str, float] = {}
    plan: list[dict] = []
    for row_name, _count in ROW_DEFS:
        frames = results[row_name].codex
        area = median_area(frames)
        proposed = math.sqrt(GLOBAL_VISUAL_TARGET_AREA / max(1.0, area))
        allow_vertical = row_name == "jumping"
        safe = row_safe_upscale(frames, allow_vertical)
        # Running and low lying rows need as much safe presence as possible;
        # large sitting/working rows are gently reduced to reduce state jumps.
        applied = min(max(proposed, ROW_SCALE_MIN), ROW_SCALE_MAX, safe)
        if row_name in {"running-right", "running-left", "failed", "jumping"}:
            applied = min(max(applied, 1.0), safe, ROW_SCALE_MAX)
        if row_name in {"running-right", "running-left"}:
            # The running cats already nearly fill the cell width. Upscaling
            # here produced 0 px left/right margins in the 32-frame master, so
            # keep them at original row-normalized size instead of chasing
            # alpha-area parity with sitting rows.
            applied = min(applied, 1.0, safe)
        if row_name == "jumping":
            # Jumping has real vertical travel; the high/low master poses need
            # more safety than the sampled Codex cells. Keep it just under
            # original size to avoid ear/tail/paw clipping at the motion apex.
            applied = min(applied, 0.98)
        factors[row_name] = applied
        plan.append(
            {
                "row_name": row_name,
                "median_alpha_area_before": round(area, 3),
                "target_alpha_area": GLOBAL_VISUAL_TARGET_AREA,
                "proposed_scale_factor": round(proposed, 6),
                "safe_scale_limit": round(safe, 6),
                "applied_scale_factor": round(applied, 6),
                "rule": "uniform row-level scale; no per-frame autoscale/bbox/recenter",
            }
        )
    return factors, plan


def write_scale_plan_csv(path: Path, plan: list[dict]) -> str:
    fieldnames = [
        "row_name",
        "median_alpha_area_before",
        "target_alpha_area",
        "proposed_scale_factor",
        "safe_scale_limit",
        "applied_scale_factor",
        "rule",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(plan)
    return str(path)


def scale_frames_row(frames: list[Image.Image], factor: float, row_name: str, allow_vertical_motion: bool = False) -> list[Image.Image]:
    if abs(factor - 1.0) < 0.005:
        return [normalize_alpha(frame.copy()) for frame in frames]
    bboxes = [alpha_bbox(frame) for frame in frames]
    valid = [bbox for bbox in bboxes if bbox]
    if not valid:
        return [Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0)) for _ in frames]
    common_center_x = float(np.median([(b[0] + b[2]) / 2 for b in valid]))
    common_baseline = float(np.median([b[3] for b in valid]))
    out: list[Image.Image] = []
    for frame, bbox in zip(frames, bboxes):
        if not bbox:
            out.append(Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0)))
            continue
        left, top, right, bottom = bbox
        crop = frame.crop((left, top, right, bottom))
        scaled_size = (
            max(1, round(crop.width * factor)),
            max(1, round(crop.height * factor)),
        )
        scaled = crop.resize(scaled_size, Image.Resampling.LANCZOS)
        center_x = (left + right) / 2
        dx = (center_x - common_center_x) * factor
        target_center_x = CELL_W / 2 + dx
        row_ground_y = CELL_H - 12 if row_name == "jumping" else GROUND_Y
        if allow_vertical_motion:
            target_bottom = row_ground_y + (bottom - common_baseline) * factor
            target_bottom = min(CELL_H - 4, target_bottom)
        else:
            target_bottom = row_ground_y
        x = round(target_center_x - scaled.width / 2)
        y = round(target_bottom - scaled.height)
        cell = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
        cell.alpha_composite(scaled, (x, y))
        out.append(normalize_alpha(cell))
    return out


def apply_global_scale_harmonization(results: dict[str, RowResult]) -> tuple[dict[str, float], list[dict]]:
    factors, plan = make_scale_adjustment_plan(results)
    for row_name, _count in ROW_DEFS:
        factor = factors[row_name]
        allow_vertical = row_name == "jumping"
        result = results[row_name]
        result.keyframes = scale_frames_row(result.keyframes, factor, row_name, allow_vertical)
        result.master = scale_frames_row(result.master, factor, row_name, allow_vertical)
        result.codex = scale_frames_row(result.codex, factor, row_name, allow_vertical)
        result.scale *= factor
    return factors, plan


def write_scale_summary(path: Path, before: list[dict], after: list[dict], plan: list[dict]) -> str:
    def row_summary(records: list[dict]) -> dict[str, dict[str, float]]:
        grouped: dict[str, list[dict]] = {}
        for rec in records:
            grouped.setdefault(rec["row_name"], []).append(rec)
        summary: dict[str, dict[str, float]] = {}
        for row, items in grouped.items():
            summary[row] = {
                "median_width": round(float(np.median([int(i["bbox_width"]) for i in items])), 2),
                "median_height": round(float(np.median([int(i["bbox_height"]) for i in items])), 2),
                "median_alpha_area": round(float(np.median([int(i["alpha_area"]) for i in items])), 2),
                "min_margin": round(
                    min(min(json.loads(i["margins"]).values()) for i in items),
                    2,
                ),
            }
        return summary

    before_s = row_summary(before)
    after_s = row_summary(after)
    lines = [
        "# Scale Comparison Summary",
        "",
        "Scope: one stable repair pass on the existing 3D calico materials.",
        "",
        "Rules enforced:",
        "- per-frame autoscale: disabled",
        "- per-frame bbox fit: disabled",
        "- per-frame recentering: disabled",
        "- row-level scale/baseline/anchor: enabled",
        "- cross-row global visual scale harmonization: enabled",
        "",
        "| row | area before | area after | median bbox before | median bbox after | applied factor | min margin after |",
        "| --- | ---: | ---: | --- | --- | ---: | ---: |",
    ]
    factor_by_row = {p["row_name"]: p["applied_scale_factor"] for p in plan}
    for row_name, _count in ROW_DEFS:
        b = before_s[row_name]
        a = after_s[row_name]
        lines.append(
            f"| {row_name} | {b['median_alpha_area']} | {a['median_alpha_area']} | "
            f"{b['median_width']}x{b['median_height']} | {a['median_width']}x{a['median_height']} | "
            f"{factor_by_row[row_name]} | {a['min_margin']} |"
        )
    lines.extend(
        [
            "",
            "Interpretation:",
            "- Standing/sitting rows were gently reduced where they visually dominated the atlas.",
            "- Running rows were kept at the largest safe row-level size because their full side profile already nearly fills the 192 px width.",
            "- Lying rows keep natural low height but are not separately autoscaled per frame.",
            "- Remaining scale differences are posture-driven, not per-frame zoom popping.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def hold_keyposes_master(keyframes: list[Image.Image], count: int, row_name: str) -> list[Image.Image]:
    if not keyframes:
        return []
    master: list[Image.Image] = []
    for idx in range(count):
        phase = (idx / count) * len(keyframes)
        key_idx = int(math.floor(phase)) % len(keyframes)
        sub = phase - math.floor(phase)
        frame = keyframes[key_idx]
        # Low-risk micro motion only; no crossfade, no optical-flow ghosting.
        if row_name in {"idle", "running", "review"}:
            dy = round(math.sin((idx / count) * 2 * math.pi) * 1.0)
            frame = shift_image(frame, 0, dy)
        elif row_name == "waving":
            dx = round(math.sin((idx / count) * 2 * math.pi) * 0.8)
            frame = shift_image(frame, dx, 0)
        elif row_name == "waiting":
            dy = 0 if sub < 0.5 else -1
            frame = shift_image(frame, 0, dy)
        master.append(normalize_alpha(frame))
    return master


def sample_codex(master: list[Image.Image], count: int) -> tuple[list[Image.Image], list[int]]:
    if count >= len(master):
        return master[:count], list(range(min(count, len(master))))
    if count == 1:
        return [master[0]], [0]
    indices = [round(i * len(master) / count) % len(master) for i in range(count)]
    return [master[i] for i in indices], indices


def save_frames(frames: list[Image.Image], root: Path, row_name: str) -> list[str]:
    out_dir = root / row_name
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for idx, frame in enumerate(frames):
        path = out_dir / f"{idx:02d}.png"
        frame.save(path)
        paths.append(str(path))
    return paths


def render_preview_frame(frame: Image.Image, scale: int = 2) -> Image.Image:
    bg = checker((CELL_W, CELL_H)).convert("RGBA")
    bg.alpha_composite(frame.convert("RGBA"))
    return bg.resize((CELL_W * scale, CELL_H * scale), Image.Resampling.NEAREST).convert("P", palette=Image.Palette.ADAPTIVE)


def save_gif(frames: list[Image.Image], out: Path, duration_ms: int = 95, scale: int = 2) -> str:
    rendered = [render_preview_frame(frame, scale=scale) for frame in frames]
    rendered[0].save(out, save_all=True, append_images=rendered[1:], duration=duration_ms, loop=0, disposal=2)
    return str(out)


def save_diff_gif(frames: list[Image.Image], out: Path, duration_ms: int = 95) -> str:
    rendered: list[Image.Image] = []
    for idx, frame in enumerate(frames):
        prev = frames[idx - 1]
        diff_alpha = ImageChops.difference(frame.getchannel("A"), prev.getchannel("A"))
        rgba = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
        arr = np.array(rgba)
        d = np.array(diff_alpha)
        arr[:, :, 0] = np.where(d > 10, 255, 0)
        arr[:, :, 1] = np.where(d > 10, 90, 0)
        arr[:, :, 2] = np.where(d > 10, 40, 0)
        arr[:, :, 3] = np.where(d > 10, np.minimum(255, d * 2), 0).astype(np.uint8)
        overlay = Image.fromarray(arr, "RGBA")
        bg = checker((CELL_W, CELL_H)).convert("RGBA")
        bg.alpha_composite(prev)
        bg.alpha_composite(overlay)
        rendered.append(bg.resize((CELL_W * 2, CELL_H * 2), Image.Resampling.NEAREST).convert("P", palette=Image.Palette.ADAPTIVE))
    rendered[0].save(out, save_all=True, append_images=rendered[1:], duration=duration_ms, loop=0, disposal=2)
    return str(out)


def frame_metrics(frames: list[Image.Image], row_name: str, scale: float, kind: str) -> dict:
    records = []
    ok = True
    previous = None
    for idx, frame in enumerate(frames):
        bbox = alpha_bbox(frame)
        if not bbox:
            ok = False
            records.append({"frame_index": idx, "ok": False, "reason": "empty"})
            previous = None
            continue
        left, top, right, bottom = bbox
        alpha = np.array(frame.getchannel("A"))
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
        width = right - left
        height = bottom - top
        margins = {
            "left": left,
            "top": top,
            "right": CELL_W - right,
            "bottom": CELL_H - bottom,
        }
        deltas = None
        if previous:
            deltas = {
                "bbox_width": width - previous["bbox_width"],
                "bbox_height": height - previous["bbox_height"],
                "center_x": center_x - previous["center_x"],
                "center_y": center_y - previous["center_y"],
                "baseline_y": bottom - previous["baseline_y"],
                "bbox_height_pct": abs(height - previous["bbox_height"]) / max(1, previous["bbox_height"]),
            }
        crop_risk = min(margins.values()) < 2
        if crop_risk:
            ok = False
        rec = {
            "row": row_name,
            "kind": kind,
            "frame_index": idx,
            "bbox": [left, top, right, bottom],
            "bbox_width": width,
            "bbox_height": height,
            "center_x": center_x,
            "center_y": center_y,
            "baseline_y": bottom,
            "scale": scale,
            "margins": margins,
            "alpha_area": int((alpha > 8).sum()),
            "crop_risk": crop_risk,
            "delta_from_previous": deltas,
        }
        records.append(rec)
        previous = rec
    return {"row": row_name, "kind": kind, "ok": ok, "frames": records}


def running_phase_report(frames: list[Image.Image], row_name: str) -> dict:
    analysis_frames = mirror_frames(frames) if row_name == "running-left" else frames
    centers = []
    for frame in analysis_frames:
        _, leg_mask, tail_mask = body_leg_tail_masks(frame)
        centers.append(
            {
                "leg_center": center_of_bbox(bbox_from_mask(leg_mask)),
                "tail_center": center_of_bbox(bbox_from_mask(tail_mask)),
            }
        )
    leg_x = [c["leg_center"][0] for c in centers]
    leg_y = [c["leg_center"][1] for c in centers]
    tail_y = [c["tail_center"][1] for c in centers]
    leg_motion_x = max(leg_x) - min(leg_x) if leg_x else 0
    leg_motion_y = max(leg_y) - min(leg_y) if leg_y else 0
    tail_motion_y = max(tail_y) - min(tail_y) if tail_y else 0
    ok = leg_motion_x >= 4 and leg_motion_y >= 2 and tail_motion_y >= 1
    return {
        "row": row_name,
        "ok": ok,
        "method": "2.5D body/leg/tail decomposition, no optical flow",
        "leg_motion_x_px": leg_motion_x,
        "leg_motion_y_px": leg_motion_y,
        "tail_motion_y_px": tail_motion_y,
        "phase_centers": centers,
        "interpretation": "leg/tail centers move across phases, indicating puppet gait rather than whole-image morphing",
    }


def visual_failure_scan(row_name: str, result: RowResult, metrics: dict) -> list[str]:
    problems: list[str] = []
    if not metrics["codex"]["ok"] or not metrics["master"]["ok"]:
        problems.append("crop risk or empty frame detected")
    if row_name in {"running-right", "running-left"}:
        phase = running_phase_report(result.codex, row_name)
        if not phase["ok"]:
            problems.append("running gait phase motion still weak")
    if row_name == "failed":
        heights = [rec.get("bbox_height", 0) for rec in metrics["codex"]["frames"]]
        widths = [rec.get("bbox_width", 0) for rec in metrics["codex"]["frames"]]
        if any(h and h < 82 for h in heights):
            problems.append("failed row contains too-flat half-body-looking frame")
        if any(w and w < 125 for w in widths):
            problems.append("failed row contains narrow/cropped-looking frame")
    if row_name != "jumping":
        for rec in metrics["codex"]["frames"][1:]:
            delta = rec.get("delta_from_previous") or {}
            if abs(delta.get("baseline_y", 0)) > 4 and row_name in {"idle", "running-right", "running-left", "running", "review"}:
                problems.append("baseline jump in stable row")
                break
    return sorted(set(problems))


def process_row(row_name: str, codex_count: int) -> RowResult:
    source = load_source_frames(row_name)
    failures_before: list[str] = []
    repaired = False
    pipeline = "clean key poses -> hold/ease master -> codex sampling"

    if row_name == "running-right":
        failures_before.append("source running row judged morph-like; switched to 2.5D puppet/rig")
        keyframes = compose_running_keyposes(source[:8])
        master = make_running_master(keyframes)
        pipeline = "clean key poses -> 2.5D body/leg/tail rig -> 32-frame master -> codex sampling"
        repaired = True
    elif row_name == "running-left":
        right_source = load_source_frames("running-right")
        right_keys = compose_running_keyposes(right_source[:8])
        keyframes = mirror_frames(right_keys)
        master = mirror_frames(make_running_master(right_keys))
        failures_before.append("source running-left regenerated from repaired running-right rig for consistency")
        pipeline = "mirrored 2.5D repaired running-right rig"
        repaired = True
    elif row_name == "jumping":
        keyframes = compose_jumping_keyposes(source)
        master = make_jumping_master(keyframes)
        failures_before.append("jumping rebuilt as proportional crouch -> takeoff -> peak -> fall -> land")
        pipeline = "clean proportional jump key poses -> 24-frame master -> 5-frame Codex row"
        repaired = True
    elif row_name == "failed":
        keyframes = compose_failed_keyposes(source)
        master = hold_keyposes_master(keyframes, MASTER_COUNTS[row_name], row_name)
        failures_before.append("failed rebuilt to remove flat half-body side strips")
        pipeline = "full-body sad sit -> sink -> readable side-roll key poses -> 24-frame master -> 8-frame Codex row"
        repaired = True
    elif row_name == "waiting":
        # Keep one readable main action in the 6-frame Codex row. The previous
        # row tried to include stretch and yawn together, which felt jumpy at
        # standard frame count, so this pass prioritizes stretch.
        keyframes = [source[i] for i in [0, 1, 2, 2, 1, 0] if i < len(source)]
        master = hold_keyposes_master(keyframes, MASTER_COUNTS[row_name], row_name)
        failures_before.append("waiting previously mixed stretch and yawn in 6 frames; simplified to one stretch loop")
        pipeline = "clean stretch key poses -> 24-frame master -> 6-frame Codex sampling"
        repaired = True
    elif row_name == "review":
        # Keep review as one observation action. Do not jump from sitting to a
        # prone pose in the same short loop.
        indices = [0, 1, 2, 3, 1, 0]
        keyframes = [source[i] for i in indices if i < len(source)]
        master = hold_keyposes_master(keyframes, MASTER_COUNTS[row_name], row_name)
        failures_before.append("review previously mixed seated and lying poses; simplified to seated observation")
        pipeline = "clean seated observation key poses -> 16-frame master -> 6-frame Codex sampling"
        repaired = True
    else:
        keyframes = source
        master = hold_keyposes_master(keyframes, MASTER_COUNTS[row_name], row_name)

    allow_vertical_motion = row_name == "jumping"
    norm_master, scale = row_normalize_frames(master, row_name, allow_vertical_motion=allow_vertical_motion)
    norm_keys, key_scale = row_normalize_frames(keyframes, row_name, allow_vertical_motion=allow_vertical_motion)
    if row_name in {"running-right", "running-left", "jumping", "failed"}:
        codex = norm_keys[:codex_count]
    else:
        codex, _ = sample_codex(norm_master, codex_count)
    norm_codex, _ = row_normalize_frames(codex, row_name, allow_vertical_motion=allow_vertical_motion, target_fill=scale)

    return RowResult(
        name=row_name,
        keyframes=norm_keys,
        master=norm_master,
        codex=norm_codex,
        scale=scale if scale else key_scale,
        pipeline=pipeline,
        repaired=repaired,
        failures_before_repair=failures_before,
        remaining_visual_problems=[],
    )


def compose_atlas(results: dict[str, RowResult]) -> str:
    atlas = Image.new("RGBA", (CELL_W * COLS, CELL_H * ROWS), (0, 0, 0, 0))
    for row_idx, (row_name, _count) in enumerate(ROW_DEFS):
        frames = results[row_name].codex
        for col, frame in enumerate(frames[:COLS]):
            atlas.alpha_composite(frame, (col * CELL_W, row_idx * CELL_H))
    out = FINAL_DIR / "spritesheet.webp"
    atlas.save(out, lossless=True, quality=100, method=6)
    return str(out)


def write_pet_json() -> str:
    data = {
        "id": PET_ID,
        "displayName": DISPLAY_NAME,
        "description": DESCRIPTION,
        "spritesheetPath": "spritesheet.webp",
        "frameSize": {"width": CELL_W, "height": CELL_H},
        "grid": {"columns": COLS, "rows": ROWS},
        "states": [
            {
                "name": row_name,
                "row": row_idx,
                "frames": count,
                "durationsMs": FRAME_DURATIONS[row_name],
            }
            for row_idx, (row_name, count) in enumerate(ROW_DEFS)
        ],
        "notes": {
            "notInstalled": True,
            "clickRuntimeSupport": "not confirmed; no unsupported click fields added",
            "animationPipeline": "clean key poses -> master preview -> Codex sampling -> row-level normalization",
        },
    }
    out = FINAL_DIR / "pet.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out)


def make_contact_sheet(results: dict[str, RowResult]) -> str:
    label_w = 150
    header_h = 30
    sheet = Image.new("RGB", (label_w + COLS * CELL_W, header_h + ROWS * CELL_H), (246, 246, 246))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for col in range(COLS):
        draw.text((label_w + col * CELL_W + 8, 8), str(col), fill=(30, 30, 30), font=font)
    for row_idx, (row_name, _count) in enumerate(ROW_DEFS):
        y = header_h + row_idx * CELL_H
        draw.text((8, y + 10), row_name, fill=(20, 20, 20), font=font)
        draw.text((8, y + 28), STATE_SEMANTICS[row_name][:28], fill=(75, 75, 75), font=font)
        for col in range(COLS):
            bg = checker((CELL_W, CELL_H)).convert("RGBA")
            if col < len(results[row_name].codex):
                bg.alpha_composite(results[row_name].codex[col])
            sheet.paste(bg.convert("RGB"), (label_w + col * CELL_W, y))
    out = QA_DIR / "contact-sheet.png"
    sheet.save(out)
    return str(out)


def make_keypose_contact_sheet(results: dict[str, RowResult]) -> str:
    label_w = 150
    max_cols = max(len(r.keyframes) for r in results.values())
    sheet = Image.new("RGB", (label_w + max_cols * CELL_W, 28 + ROWS * CELL_H), (246, 246, 246))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for row_idx, (row_name, _count) in enumerate(ROW_DEFS):
        y = 28 + row_idx * CELL_H
        draw.text((8, y + 10), row_name, fill=(20, 20, 20), font=font)
        for col, frame in enumerate(results[row_name].keyframes):
            bg = checker((CELL_W, CELL_H)).convert("RGBA")
            bg.alpha_composite(frame)
            sheet.paste(bg.convert("RGB"), (label_w + col * CELL_W, y))
    out = QA_DIR / "keypose-contact-sheet.png"
    sheet.save(out)
    return str(out)


def write_preview_html(preview_paths: dict[str, dict[str, str]], contact_sheet: str) -> str:
    rows = []
    for row_name, _count in ROW_DEFS:
        rel_master = Path(preview_paths[row_name]["master"]).relative_to(OUT).as_posix()
        rel_codex = Path(preview_paths[row_name]["codex"]).relative_to(OUT).as_posix()
        rel_diff = Path(preview_paths[row_name]["diff"]).relative_to(OUT).as_posix()
        rows.append(
            f"<section><h2>{row_name}</h2><div class='grid'>"
            f"<figure><figcaption>master</figcaption><img src='{rel_master}'></figure>"
            f"<figure><figcaption>Codex</figcaption><img src='{rel_codex}'></figure>"
            f"<figure><figcaption>motion diff</figcaption><img src='{rel_diff}'></figure>"
            f"</div></section>"
        )
    rel_contact = Path(contact_sheet).relative_to(OUT).as_posix()
    html = f"""<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<title>三花猫猫 3D motionfix all preview</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f7f7f7; color: #222; }}
h1 {{ font-size: 24px; }}
h2 {{ margin-top: 28px; }}
.grid {{ display: grid; grid-template-columns: repeat(3, minmax(240px, 1fr)); gap: 14px; }}
figure {{ margin: 0; padding: 12px; background: #fff; border: 1px solid #ddd; }}
img {{ max-width: 100%; image-rendering: auto; }}
figcaption {{ font-size: 13px; color: #555; margin-bottom: 8px; }}
</style>
<h1>三花猫猫 3D motionfix all</h1>
<p>Not installed. Fixed 8x9 Codex atlas. Running rows use a 2.5D body/leg/tail rig; no optical-flow frames are used as final Codex keyframes.</p>
<p><a href="{rel_contact}">contact sheet</a></p>
{''.join(rows)}
</html>
"""
    out = OUT / "preview.html"
    out.write_text(html, encoding="utf-8")
    return str(out)


def validate_outputs(spritesheet: str, pet_json: str, results: dict[str, RowResult]) -> dict:
    ok = True
    issues: list[str] = []
    atlas = Image.open(spritesheet).convert("RGBA")
    if atlas.size != (CELL_W * COLS, CELL_H * ROWS):
        ok = False
        issues.append(f"spritesheet size mismatch: {atlas.size}")
    data = json.loads(Path(pet_json).read_text(encoding="utf-8"))
    if data.get("spritesheetPath") != "spritesheet.webp":
        ok = False
        issues.append("spritesheetPath is not spritesheet.webp")
    if data.get("grid") != {"columns": COLS, "rows": ROWS}:
        ok = False
        issues.append("grid mismatch")
    for row_idx, (row_name, count) in enumerate(ROW_DEFS):
        if len(results[row_name].codex) != count:
            ok = False
            issues.append(f"{row_name} codex count mismatch")
        for col in range(count, COLS):
            cell = atlas.crop((col * CELL_W, row_idx * CELL_H, (col + 1) * CELL_W, (row_idx + 1) * CELL_H))
            if np.array(cell.getchannel("A")).max() != 0:
                ok = False
                issues.append(f"{row_name} unused cell {col} is not transparent")
    return {"ok": ok, "issues": issues, "atlas_size": list(atlas.size)}


def write_changelog(results: dict[str, RowResult]) -> str:
    lines = [
        "# Motionfix All Changelog",
        "",
        "- Froze the selected 3D calico cat visual identity.",
        "- Stopped using optical flow as the primary motion source.",
        "- Added key-pose-first processing for all 9 Codex states.",
        "- Rebuilt running-right and running-left with a 2.5D body/leg/tail rig.",
        "- Added measured before/after scale audits and one global row-level visual harmonization pass.",
        "- Simplified waiting to stretch-only in the Codex row and review to one seated observation loop.",
        "- Kept final Codex atlas at 1536x1872, 8x9, 192x208 cells.",
        "- Did not install or overwrite the current Codex pet.",
        "",
        "## Per-row pipeline",
    ]
    for row_name, _count in ROW_DEFS:
        result = results[row_name]
        lines.append(f"- {row_name}: {result.pipeline}")
    out = OUT / "CHANGELOG.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out)


def main() -> None:
    clean_output()
    results: dict[str, RowResult] = {}
    for row_name, codex_count in ROW_DEFS:
        results[row_name] = process_row(row_name, codex_count)

    scale_audit_before_records: list[dict] = []
    for row_name, _count in ROW_DEFS:
        scale_audit_before_records.extend(row_metrics_for_audit(results[row_name].codex, row_name, 1.0))
    scale_audit_before = write_audit_csv(QA_DIR / "scale_audit_before.csv", scale_audit_before_records)

    global_scale_factors, scale_plan = apply_global_scale_harmonization(results)
    scale_adjustment_plan = write_scale_plan_csv(QA_DIR / "scale_adjustment_plan.csv", scale_plan)

    scale_audit_after_records: list[dict] = []
    for row_name, _count in ROW_DEFS:
        scale_audit_after_records.extend(
            row_metrics_for_audit(results[row_name].codex, row_name, global_scale_factors[row_name])
        )
    scale_audit_after = write_audit_csv(QA_DIR / "scale_audit_after.csv", scale_audit_after_records)
    scale_summary = write_scale_summary(
        QA_DIR / "scale_comparison_summary.md",
        scale_audit_before_records,
        scale_audit_after_records,
        scale_plan,
    )

    preview_paths: dict[str, dict[str, str]] = {}
    stability: dict[str, dict[str, dict]] = {}
    action_diff_report: dict[str, dict] = {}
    for row_name, _count in ROW_DEFS:
        result = results[row_name]
        save_frames(result.master, MASTER_DIR, row_name)
        save_frames(result.codex, CODEX_DIR, row_name)
        master_gif = save_gif(result.master, PREVIEW_DIR / f"{row_name}-master.gif", duration_ms=70)
        codex_gif = save_gif(result.codex, PREVIEW_DIR / f"{row_name}-codex.gif", duration_ms=FRAME_DURATIONS[row_name][0])
        diff_gif = save_diff_gif(result.codex, DIFF_DIR / f"{row_name}-codex-diff.gif", duration_ms=FRAME_DURATIONS[row_name][0])
        preview_paths[row_name] = {"master": master_gif, "codex": codex_gif, "diff": diff_gif}
        stability[row_name] = {
            "master": frame_metrics(result.master, row_name, result.scale, "master"),
            "codex": frame_metrics(result.codex, row_name, result.scale, "codex"),
        }
        result.remaining_visual_problems = visual_failure_scan(row_name, result, stability[row_name])
        action_diff_report[row_name] = {
            "codex_diff_gif": diff_gif,
            "semantic_goal": STATE_SEMANTICS[row_name],
            "pipeline": result.pipeline,
            "running_phase_report": running_phase_report(result.codex, row_name) if row_name in {"running-right", "running-left"} else None,
        }

    spritesheet = compose_atlas(results)
    pet_json = write_pet_json()
    contact_sheet = make_contact_sheet(results)
    keypose_contact = make_keypose_contact_sheet(results)
    preview_html = write_preview_html(preview_paths, contact_sheet)
    validation = validate_outputs(spritesheet, pet_json, results)

    review = {
        "ready_for_user_review": True,
        "installed": False,
        "output_dir": str(OUT),
        "visual_identity": "frozen from selected 3D calico cat; no redesign",
        "codex_contract": "1536x1872, 8 columns x 9 rows, 192x208 cells",
        "movement": "desktop/window movement intentionally deferred",
        "optical_flow": {
            "used": False,
            "reason": "previous optical-flow master produced morphing and soft legs; this version uses key poses and 2.5D rig for running rows",
        },
        "normalization": {
            "per_frame_autoscale": False,
            "per_frame_bbox_fit": False,
            "per_frame_recenter": False,
            "row_level_scale": True,
            "row_level_baseline": True,
            "row_level_anchor": True,
            "global_visual_scale_harmonization": True,
        },
        "scale_audit": {
            "before": scale_audit_before,
            "adjustment_plan": scale_adjustment_plan,
            "after": scale_audit_after,
            "summary": scale_summary,
        },
        "states": {
            row_name: {
                "pipeline": results[row_name].pipeline,
                "repaired": results[row_name].repaired,
                "failures_before_repair": results[row_name].failures_before_repair,
                "remaining_visual_problems": results[row_name].remaining_visual_problems,
                "master_preview": preview_paths[row_name]["master"],
                "codex_preview": preview_paths[row_name]["codex"],
                "motion_diff": preview_paths[row_name]["diff"],
            }
            for row_name, _ in ROW_DEFS
        },
    }

    frame_report = {
        "ok": validation["ok"] and all(not results[row_name].remaining_visual_problems for row_name, _ in ROW_DEFS),
        "normalization": review["normalization"],
        "stability": stability,
    }

    validation_path = QA_DIR / "validation.json"
    frame_report_path = QA_DIR / "frame_stability_report.json"
    review_path = QA_DIR / "review.json"
    diff_report_path = QA_DIR / "action_diff_report.json"
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    frame_report_path.write_text(json.dumps(frame_report, ensure_ascii=False, indent=2), encoding="utf-8")
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    diff_report_path.write_text(json.dumps(action_diff_report, ensure_ascii=False, indent=2), encoding="utf-8")
    changelog = write_changelog(results)

    run_log_lines = [
        "motionfix all states",
        f"output_dir={OUT}",
        "installed=false",
        "visual_identity=frozen",
        "optical_flow_used=false",
        "running_rows=2.5D body/leg/tail rig",
        "per_frame_autoscale=false",
        "row_level_scale_baseline_anchor=true",
        "global_visual_scale_harmonization=true",
        f"scale_audit_before={scale_audit_before}",
        f"scale_adjustment_plan={scale_adjustment_plan}",
        f"scale_audit_after={scale_audit_after}",
        f"scale_comparison_summary={scale_summary}",
        f"validation_ok={validation['ok']}",
        f"frame_stability_ok={frame_report['ok']}",
        f"review_ready=true",
    ]
    for row_name, _ in ROW_DEFS:
        run_log_lines.append(f"{row_name}.remaining={','.join(results[row_name].remaining_visual_problems) or 'none'}")
    run_log = OUT / "run.log"
    run_log.write_text("\n".join(run_log_lines) + "\n", encoding="utf-8")

    summary = {
        "output_dir": str(OUT),
        "spritesheet": spritesheet,
        "pet_json": pet_json,
        "contact_sheet": contact_sheet,
        "keypose_contact_sheet": keypose_contact,
        "preview_html": preview_html,
        "validation": str(validation_path),
        "frame_stability_report": str(frame_report_path),
        "scale_audit_before": scale_audit_before,
        "scale_adjustment_plan": scale_adjustment_plan,
        "scale_audit_after": scale_audit_after,
        "scale_comparison_summary": scale_summary,
        "review": str(review_path),
        "action_diff_report": str(diff_report_path),
        "changelog": changelog,
        "run_log": str(run_log),
        "validation_ok": validation["ok"],
        "frame_stability_ok": frame_report["ok"],
        "remaining_visual_problems": {
            row_name: results[row_name].remaining_visual_problems for row_name, _ in ROW_DEFS
        },
        "previews": preview_paths,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
