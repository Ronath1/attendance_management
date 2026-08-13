from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt

from attendance.database import attendance_for_student, connect


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize attendance for one student")
    parser.add_argument("student_index", help="Student index, e.g. 10000409")
    parser.add_argument("--db", default="outputs/attendance.db", help="SQLite database path")
    parser.add_argument("--out", default=None, help="Output chart path")
    args = parser.parse_args()

    conn = connect(args.db)
    rows = attendance_for_student(conn, args.student_index)
    if not rows:
        raise SystemExit(f"No attendance found for student {args.student_index}. Run sams.py first.")

    name = rows[0]["name"]
    sessions = [row["session_id"] for row in rows]
    values = [int(row["present"]) for row in rows]
    colors = ["#2e7d32" if value else "#c62828" for value in values]
    present_count = sum(values)
    percentage = 100 * present_count / len(values)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), gridspec_kw={"width_ratios": [2.2, 1]})
    axes[0].bar(sessions, values, color=colors)
    axes[0].set_ylim(0, 1.2)
    axes[0].set_yticks([0, 1], ["Absent", "Present"])
    axes[0].set_title(f"Attendance Timeline: {name}")
    axes[0].set_xlabel("Session / image")
    axes[0].tick_params(axis="x", rotation=35)
    axes[0].grid(axis="y", alpha=0.25)

    axes[1].pie(
        [present_count, len(values) - present_count],
        labels=["Present", "Absent"],
        colors=["#2e7d32", "#c62828"],
        autopct="%1.0f%%",
        startangle=90,
    )
    axes[1].set_title(f"{percentage:.1f}% present")

    fig.tight_layout()
    out = Path(args.out or f"outputs/charts/{args.student_index}_attendance.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)
    print(f"Chart saved: {out.resolve()}")


if __name__ == "__main__":
    main()
