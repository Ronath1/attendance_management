from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

from attendance.database import connect, save_attendance, upsert_students
from attendance.processor import (
    estimate_student_rows,
    extract_students_from_sheet,
    process_sheet,
    session_id_from_image,
)
from attendance.students import load_students, placeholder_students


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def process_batch(
    folder_path: str | Path,
    info_xml_path: str | Path | None = None,
    db_path: str | Path = "outputs/attendance.db",
    threshold: float = 0.03,
    debug_dir: str | Path = "outputs/debug",
    rows: int | None = None,
    no_ocr: bool = False,
) -> dict:
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        raise ValueError(f"Image folder does not exist or is not a directory: {folder}")

    # Filter and sort supported image files alphabetically
    image_files = sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
    )

    if not image_files:
        print(f"No PNG, JPG, or JPEG images found in: {folder}")
        return {"total": 0, "success": 0, "failed": 0, "results": []}

    print(f"Found {len(image_files)} signing-sheet image(s) in '{folder.resolve()}'.\n")

    students = None
    if info_xml_path and Path(info_xml_path).exists():
        students = load_students(info_xml_path)

    conn = connect(db_path)
    try:
        if students:
            upsert_students(conn, students)

        successful_count = 0
        failed_count = 0
        batch_summary: List[Tuple[str, str, str]] = []

        for idx, img_path in enumerate(image_files, start=1):
            print(f"[{idx}/{len(image_files)}] Processing image: {img_path.name}...")
            try:
                current_students = students
                if current_students is None:
                    sheet_rows = rows
                    if sheet_rows is None:
                        sheet_rows = estimate_student_rows(img_path)
                        if sheet_rows <= 0:
                            raise ValueError("Could not auto-detect student rows. Specify --rows or provide info.xml")
                    if no_ocr:
                        current_students = placeholder_students(sheet_rows)
                    else:
                        current_students = extract_students_from_sheet(img_path, sheet_rows)

                    upsert_students(conn, current_students)

                session_id = session_id_from_image(img_path)
                if not info_xml_path or not Path(info_xml_path).exists():
                    session_id = f"{session_id}_rows_only"

                img_debug_dir = debug_dir
                if not info_xml_path or not Path(info_xml_path).exists():
                    img_debug_dir = str(Path(debug_dir) / f"{session_id}_rows_only")

                detection_results, _ = process_sheet(
                    img_path,
                    current_students,
                    debug_dir=img_debug_dir,
                    threshold_ratio=threshold,
                )

                db_rows = [
                    {
                        "session_id": session_id,
                        "image_file": str(img_path.resolve()),
                        "student_index": r.student.index,
                        "present": 1 if r.present else 0,
                        "ink_pixels": r.ink_pixels,
                        "ink_ratio": r.ink_ratio,
                        "confidence": r.confidence,
                    }
                    for r in detection_results
                ]

                save_attendance(conn, db_rows)
                successful_count += 1
                present_cnt = sum(1 for r in detection_results if r.present)
                total_cnt = len(detection_results)
                batch_summary.append((img_path.name, "SUCCESS", f"{present_cnt}/{total_cnt} Present (Session: {session_id})"))
                print(f"   --> Success: {present_cnt}/{total_cnt} present. Session ID: {session_id}\n")

            except Exception as exc:
                failed_count += 1
                error_msg = str(exc)
                batch_summary.append((img_path.name, "FAILED", error_msg))
                print(f"   --> ERROR processing '{img_path.name}': {error_msg}\n")
                continue
    finally:
        conn.close()

    print("=" * 72)
    print("BATCH PROCESSING FINAL SUMMARY")
    print("=" * 72)
    print(f"Total Images Discovered : {len(image_files)}")
    print(f"Successfully Processed : {successful_count}")
    print(f"Failed / Skipped      : {failed_count}")
    print("-" * 72)
    print(f"{'Filename':<30} {'Status':<10} {'Details'}")
    print("-" * 72)
    for filename, status, details in batch_summary:
        print(f"{filename:<30} {status:<10} {details}")
    print("=" * 72)

    return {
        "total": len(image_files),
        "success": successful_count,
        "failed": failed_count,
        "results": batch_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch Processing for Student Signing Sheets")
    parser.add_argument("folder", help="Folder containing signing-sheet images (.png, .jpg, .jpeg)")
    parser.add_argument("info_xml", nargs="?", default="data/info.xml", help="Path to student details info.xml (default: data/info.xml)")
    parser.add_argument("--db", default="outputs/attendance.db", help="SQLite database path")
    parser.add_argument("--debug-dir", default="outputs/debug", help="Directory for processing screenshots")
    parser.add_argument("--threshold", type=float, default=0.03, help="Ink ratio threshold for present/absent")
    parser.add_argument("--rows", type=int, default=None, help="Row count if no XML is provided")
    parser.add_argument("--no-ocr", action="store_true", help="Use ROW001 labels instead of OCR if no XML")
    args = parser.parse_args()

    process_batch(
        folder_path=args.folder,
        info_xml_path=args.info_xml,
        db_path=args.db,
        threshold=args.threshold,
        debug_dir=args.debug_dir,
        rows=args.rows,
        no_ocr=args.no_ocr,
    )


if __name__ == "__main__":
    main()
