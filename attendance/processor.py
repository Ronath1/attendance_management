from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import re
import unicodedata

import cv2
import numpy as np

from .students import Student


@dataclass
class DetectionResult:
    student: Student
    present: bool
    ink_pixels: int
    ink_ratio: float
    confidence: float
    roi: tuple[int, int, int, int]


def _group_positions(mask: np.ndarray, axis: int, min_fraction: float, gap: int = 8) -> list[int]:
    projection = np.count_nonzero(mask, axis=axis)
    limit = int(mask.shape[1 - axis] * min_fraction)
    raw = np.where(projection >= limit)[0]
    if len(raw) == 0:
        return []

    groups: list[list[int]] = [[int(raw[0])]]
    for value in raw[1:]:
        value = int(value)
        if value - groups[-1][-1] <= gap:
            groups[-1].append(value)
        else:
            groups.append([value])

    return [int(round(sum(g) / len(g))) for g in groups]


def _best_student_rows(y_lines: list[int], image_height: int, expected_rows: int) -> list[int] | None:
    needed = expected_rows + 1
    if len(y_lines) < needed:
        return None

    best: tuple[float, list[int]] | None = None
    for start in range(0, len(y_lines) - needed + 1):
        candidate = y_lines[start : start + needed]
        intervals = np.diff(candidate)
        median = float(np.median(intervals))
        if median <= 12:
            continue
        regularity = float(np.std(intervals) / max(median, 1.0))
        vertical_pos = abs(((candidate[0] + candidate[-1]) / 2 / image_height) - 0.55)
        score = regularity + vertical_pos
        if best is None or score < best[0]:
            best = (score, candidate)
    return best[1] if best else None


def _fallback_geometry(width: int, height: int, expected_rows: int) -> tuple[list[int], list[int]]:
    y_top = int(height * 0.385)
    y_bottom = int(height * 0.585)
    row_h = (y_bottom - y_top) / expected_rows
    y_lines = [int(round(y_top + i * row_h)) for i in range(expected_rows + 1)]

    x_lines = [
        int(width * 0.115),
        int(width * 0.205),
        int(width * 0.360),
        int(width * 0.445),
        int(width * 0.710),
        int(width * 0.870),
    ]
    return y_lines, x_lines


def _table_bbox_from_grid(grid_mask: np.ndarray) -> tuple[int, int, int, int] | None:
    height, width = grid_mask.shape[:2]
    closed = cv2.morphologyEx(
        grid_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11)),
        iterations=1,
    )
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[tuple[float, tuple[int, int, int, int]]] = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w < width * 0.45 or h < height * 0.10:
            continue
        if y < height * 0.25 or y > height * 0.75:
            continue
        aspect = w / max(h, 1)
        if aspect < 2.0:
            continue
        score = (w * h) + y * 120
        candidates.append((score, (x, y, w, h)))

    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _detect_geometry(image: np.ndarray, expected_rows: int) -> tuple[list[int], list[int], np.ndarray]:
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    binary = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 11
    )

    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, width // 18), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(30, height // 24)))
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=1)
    grid = cv2.bitwise_or(horizontal, vertical)

    bbox = _table_bbox_from_grid(grid)
    if bbox is not None:
        x, y, bw, bh = bbox
        horizontal_band = horizontal[
            max(0, y - 5) : min(height, y + bh + 5),
            max(0, x - 5) : min(width, x + bw + 5),
        ]
        detected_rows = _group_positions(horizontal_band, axis=1, min_fraction=0.05, gap=6)
        detected_rows = [value + max(0, y - 5) for value in detected_rows]

        use_detected_rows = False
        if len(detected_rows) == expected_rows + 1:
            intervals = np.diff(detected_rows)
            median_interval = float(np.median(intervals))
            if median_interval > 0 and float(np.max(intervals)) / median_interval < 1.30:
                use_detected_rows = True

        if use_detected_rows:
            row_lines = detected_rows
        elif len(detected_rows) == expected_rows + 1:
            # Sometimes the header-bottom line is weak, so detection returns:
            # table top, row1 bottom, row2 bottom... Estimate only that missing
            # header boundary, then keep the detected student-row bottoms.
            estimated_header_bottom = int(round(y + (bh / (expected_rows + 1))))
            if y < estimated_header_bottom < detected_rows[1]:
                row_lines = [estimated_header_bottom] + detected_rows[1:]
            else:
                all_lines = [int(round(y + (bh * i / (expected_rows + 1)))) for i in range(expected_rows + 2)]
                row_lines = all_lines[1:]
        else:
            # Student tables have one header row plus one row per student.
            all_lines = [int(round(y + (bh * i / (expected_rows + 1)))) for i in range(expected_rows + 2)]
            row_lines = all_lines[1:]

        vertical_band = vertical[max(0, y - 8) : min(height, y + bh + 8), max(0, x - 8) : min(width, x + bw + 8)]
        detected_x = _group_positions(vertical_band, axis=0, min_fraction=0.28)
        detected_x = [value + max(0, x - 8) for value in detected_x]

        if len(detected_x) >= 6:
            detected_x = sorted(detected_x)
            x_lines = [detected_x[0], *detected_x[-5:]]
        else:
            x_lines = [
                x,
                int(x + bw * 0.12),
                int(x + bw * 0.31),
                int(x + bw * 0.42),
                int(x + bw * 0.76),
                x + bw,
            ]

        return row_lines, x_lines, grid

    y_lines = _group_positions(horizontal, axis=1, min_fraction=0.22)
    row_lines = _best_student_rows(y_lines, height, expected_rows)

    if row_lines is None:
        row_lines, x_lines = _fallback_geometry(width, height, expected_rows)
        return row_lines, x_lines, grid

    y1, y2 = row_lines[0], row_lines[-1]
    vertical_band = vertical[max(0, y1 - 5) : min(height, y2 + 5), :]
    x_lines = _group_positions(vertical_band, axis=0, min_fraction=0.45)

    if len(x_lines) < 6:
        _, x_lines = _fallback_geometry(width, height, expected_rows)
    else:
        x_lines = sorted(x_lines)
        # The detected verticals may include nearby lecture-table lines; keep the student-table span.
        wide_groups = []
        for i in range(len(x_lines) - 5):
            span = x_lines[i + 5] - x_lines[i]
            if span > width * 0.45:
                wide_groups.append(x_lines[i : i + 6])
        x_lines = max(wide_groups, key=lambda xs: xs[-1] - xs[0]) if wide_groups else x_lines[-6:]

    return row_lines, x_lines, grid


def estimate_student_rows(image_path: str | Path) -> int:
    image_path = Path(image_path)
    original = cv2.imread(str(image_path))
    if original is None:
        raise ValueError(f"Could not read image: {image_path}")

    max_width = 1400
    scale = min(1.0, max_width / original.shape[1])
    image = cv2.resize(original, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    height, width = image.shape[:2]

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    binary = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 11
    )
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, width // 18), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(30, height // 24)))
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=1)
    grid = cv2.bitwise_or(horizontal, vertical)

    bbox = _table_bbox_from_grid(grid)
    if bbox is None:
        return 0

    x, y, bw, bh = bbox
    horizontal_band = horizontal[
        max(0, y - 5) : min(height, y + bh + 5),
        max(0, x - 5) : min(width, x + bw + 5),
    ]
    detected_rows = _group_positions(horizontal_band, axis=1, min_fraction=0.05, gap=6)
    if len(detected_rows) >= 3:
        return len(detected_rows) - 1
    return 0


def _ocr_cell(cell: np.ndarray, numeric: bool = False) -> str:
    try:
        import pytesseract
    except Exception:
        return ""

    gray = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2.4, fy=2.4, interpolation=cv2.INTER_CUBIC)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    config = "--psm 7"
    if numeric:
        config += " -c tessedit_char_whitelist=0123456789"

    text = pytesseract.image_to_string(thresh, config=config)
    text = " ".join(text.replace("|", " ").replace("\n", " ").split())
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    if numeric:
        text = re.sub(r"\D", "", text)
        if len(text) == 8 and text.startswith("7"):
            text = "1" + text[1:]
    else:
        text = re.sub(r"[^A-Za-z0-9 .'-]", " ", text)
        text = " ".join(text.split())
    return text.strip(" .,:;")


def extract_students_from_sheet(image_path: str | Path, row_count: int | None = None) -> list[Student]:
    image_path = Path(image_path)
    original = cv2.imread(str(image_path))
    if original is None:
        raise ValueError(f"Could not read image: {image_path}")

    if row_count is None:
        row_count = estimate_student_rows(image_path)
    if row_count <= 0:
        raise ValueError("Could not auto-detect student rows for OCR")

    max_width = 1400
    scale = min(1.0, max_width / original.shape[1])
    image = cv2.resize(original, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    row_lines, x_lines, _ = _detect_geometry(image, row_count)
    x_lines = sorted(x_lines)

    students: list[Student] = []
    for i in range(row_count):
        y1, y2 = row_lines[i], row_lines[i + 1]
        row_h = y2 - y1
        yy1 = max(0, y1 + int(row_h * 0.08))
        yy2 = min(image.shape[0], y2 - int(row_h * 0.08))

        index_crop = image[yy1:yy2, x_lines[1] + 4 : x_lines[2] - 4]
        title_crop = image[yy1:yy2, x_lines[2] + 4 : x_lines[3] - 4]
        name_crop = image[yy1:yy2, x_lines[3] + 4 : x_lines[4] - 4]

        index = _ocr_cell(index_crop, numeric=True)
        title = _ocr_cell(title_crop)
        name = _ocr_cell(name_crop)

        if not index:
            index = f"ROW{i + 1:03d}"
        if not name:
            name = f"Student Row {i + 1}"

        students.append(Student(index=index, title=title, name=name))

    return students


def _ink_mask(roi: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    blue = cv2.inRange(hsv, np.array([85, 35, 35]), np.array([145, 255, 255]))
    dark_colored = cv2.inRange(hsv, np.array([0, 30, 0]), np.array([179, 255, 170]))
    dark_gray = cv2.inRange(gray, 0, 85)
    mask = cv2.bitwise_or(blue, cv2.bitwise_or(dark_colored, dark_gray))

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    return mask


def process_sheet(
    image_path: str | Path,
    students: list[Student],
    debug_dir: str | Path | None = None,
    threshold_ratio: float = 0.03,
) -> tuple[list[DetectionResult], dict]:
    image_path = Path(image_path)
    original = cv2.imread(str(image_path))
    if original is None:
        raise ValueError(f"Could not read image: {image_path}")

    max_width = 1400
    scale = min(1.0, max_width / original.shape[1])
    image = cv2.resize(original, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    h, w = image.shape[:2]

    row_lines, x_lines, grid_mask = _detect_geometry(image, len(students))
    signature_left, signature_right = sorted(x_lines)[-2], sorted(x_lines)[-1]

    results: list[DetectionResult] = []
    overlay = image.copy()
    debug_masks: list[np.ndarray] = []

    for i, student in enumerate(students):
        y1, y2 = row_lines[i], row_lines[i + 1]
        pad_x = max(12, int((signature_right - signature_left) * 0.12))
        pad_y = max(6, int((y2 - y1) * 0.20))
        x1 = max(0, signature_left + pad_x)
        x2 = min(w, signature_right - pad_x)
        yy1 = max(0, y1 + pad_y)
        yy2 = min(h, y2 - pad_y)

        roi = image[yy1:yy2, x1:x2]
        mask = _ink_mask(roi)
        ink_pixels = int(np.count_nonzero(mask))
        ink_ratio = ink_pixels / max(mask.size, 1)
        confidence = min(1.0, ink_ratio / max(threshold_ratio * 2.0, 0.0001))
        present = ink_ratio >= threshold_ratio

        color = (40, 180, 40) if present else (40, 40, 220)
        cv2.rectangle(overlay, (x1, yy1), (x2, yy2), color, 3)
        cv2.putText(
            overlay,
            f"{student.index} {'P' if present else 'A'} {ink_ratio:.3f}",
            (x1, max(20, yy1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )
        debug_masks.append(mask)

        results.append(
            DetectionResult(
                student=student,
                present=present,
                ink_pixels=ink_pixels,
                ink_ratio=ink_ratio,
                confidence=confidence,
                roi=(x1, yy1, x2, yy2),
            )
        )

    if debug_dir:
        debug_root = Path(debug_dir) / image_path.stem
        debug_root.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_root / "01_resized_input.jpg"), image)
        cv2.imwrite(str(debug_root / "02_detected_grid.png"), grid_mask)
        cv2.imwrite(str(debug_root / "03_signature_rois.jpg"), overlay)
        for idx, mask in enumerate(debug_masks, 1):
            cv2.imwrite(str(debug_root / f"mask_row_{idx:02d}.png"), mask)

    metadata = {
        "image_width": w,
        "image_height": h,
        "row_lines": row_lines,
        "x_lines": x_lines,
        "signature_column": [signature_left, signature_right],
        "scale": scale,
        "threshold_ratio": threshold_ratio,
    }
    return results, metadata


def session_id_from_image(image_path: str | Path) -> str:
    stem = Path(image_path).stem
    return stem.replace(" ", "_")
