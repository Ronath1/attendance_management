from __future__ import annotations

import argparse
import csv
from pathlib import Path

from attendance.database import connect, save_attendance, summary, upsert_students
from attendance.processor import estimate_student_rows, extract_students_from_sheet, process_sheet, session_id_from_image
from attendance.students import load_students, placeholder_students


def main() -> None:
    parser = argparse.ArgumentParser(description="Student Attendance Management System")
    parser.add_argument("image", help="Signing-sheet image path")
    parser.add_argument("info_xml", nargs="?", help="Optional student info XML path")
    parser.add_argument("--rows", type=int, default=None, help="Student row count when no XML is provided")
    parser.add_argument("--no-ocr", action="store_true", help="Use ROW001 labels instead of OCR in image-only mode")
    parser.add_argument("--db", default="outputs/attendance.db", help="SQLite database path")
    parser.add_argument("--debug-dir", default="outputs/debug", help="Directory for processing screenshots")
    parser.add_argument("--csv", default=None, help="Optional CSV output path for this sheet")
    parser.add_argument("--threshold", type=float, default=0.03, help="Ink ratio threshold for present/absent")
    args = parser.parse_args()

    if args.info_xml:
        students = load_students(args.info_xml)
    else:
        if args.rows is None:
            args.rows = estimate_student_rows(args.image)
            if args.rows <= 0:
                raise SystemExit("Could not auto-detect rows. Use --rows, e.g. python sams.py sheet.png --rows 30")
        if args.no_ocr:
            students = placeholder_students(args.rows)
        else:
            students = extract_students_from_sheet(args.image, args.rows)

    session_id = session_id_from_image(args.image)
    if not args.info_xml:
        session_id = f"{session_id}_rows_only"
    debug_dir = args.debug_dir
    if not args.info_xml:
        debug_dir = str(Path(args.debug_dir) / f"{session_id_from_image(args.image)}_rows_only")

    results, metadata = process_sheet(
        args.image,
        students,
        debug_dir=debug_dir,
        threshold_ratio=args.threshold,
    )

    rows = [
        {
            "session_id": session_id,
            "image_file": str(Path(args.image).resolve()),
            "student_index": r.student.index,
            "present": 1 if r.present else 0,
            "ink_pixels": r.ink_pixels,
            "ink_ratio": r.ink_ratio,
            "confidence": r.confidence,
        }
        for r in results
    ]

    conn = connect(args.db)
    upsert_students(conn, students)
    save_attendance(conn, rows)

    print(f"Processed: {args.image}")
    print(f"Session:   {session_id}")
    print(f"DB:        {Path(args.db).resolve()}")
    print(f"Debug:     {Path(debug_dir).resolve() / Path(args.image).stem}")
    print()
    print(f"{'Index':<10} {'Name':<36} {'Status':<8} {'Ink ratio':>9}")
    print("-" * 68)
    for result in results:
        status = "Present" if result.present else "Absent"
        print(f"{result.student.index:<10} {result.student.name:<36} {status:<8} {result.ink_ratio:>9.4f}")

    if args.csv:
        out = Path(args.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["session_id", "student_index", "name", "present", "ink_pixels", "ink_ratio"])
            for result in results:
                writer.writerow(
                    [
                        session_id,
                        result.student.index,
                        result.student.name,
                        int(result.present),
                        result.ink_pixels,
                        f"{result.ink_ratio:.6f}",
                    ]
                )
        print(f"\nCSV:       {out.resolve()}")

    print("\nOverall summary")
    print("-" * 68)
    for row in summary(conn):
        print(
            f"{row['student_index']:<10} {row['name']:<36} "
            f"{row['present_count'] or 0}/{row['sessions'] or 0} present "
            f"({row['percentage'] or 0:.2f}%)"
        )

    print("\nProcessing metadata")
    print(f"Rows detected at y={metadata['row_lines']}")
    print(f"Signature column x={metadata['signature_column']}")


if __name__ == "__main__":
    main()
