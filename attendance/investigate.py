from __future__ import annotations

import argparse
from pathlib import Path

from attendance.database import attendance_for_student, connect


def main() -> None:
    parser = argparse.ArgumentParser(description="Basic signature consistency investigation")
    parser.add_argument("student_index", help="Student index to investigate")
    parser.add_argument("--db", default="outputs/attendance.db", help="SQLite database path")
    args = parser.parse_args()

    conn = connect(args.db)
    rows = attendance_for_student(conn, args.student_index)
    present_rows = [row for row in rows if row["present"]]
    if not rows:
        raise SystemExit(f"No attendance found for student {args.student_index}. Run sams.py first.")

    print(f"Investigation for {args.student_index} - {rows[0]['name']}")
    print("-" * 72)

    if len(present_rows) < 2:
        print("Not enough present signatures to compare. Collect more signed sheets first.")
        return

    ratios = [float(row["ink_ratio"]) for row in present_rows]
    avg = sum(ratios) / len(ratios)
    tolerance = max(avg * 0.70, 0.01)

    for row in present_rows:
        ratio = float(row["ink_ratio"])
        diff = abs(ratio - avg)
        flag = "CHECK" if diff > tolerance else "OK"
        print(
            f"{row['session_id']:<16} ink_ratio={ratio:.4f} "
            f"avg_diff={diff:.4f} {flag}"
        )

    print()
    print("Note: this is a simple prototype check based on signature ink density.")
    print("For higher marks, extend this with saved signature ROIs and shape matching.")


if __name__ == "__main__":
    main()
