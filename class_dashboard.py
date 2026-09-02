from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np

from attendance.database import connect


def generate_class_dashboard(
    db_path: str | Path = "outputs/attendance.db",
    out_chart_path: str | Path = "outputs/charts/class_attendance_dashboard.png",
    out_csv_path: str | Path = "outputs/class_attendance_summary.csv",
) -> dict:
    conn = connect(db_path)
    try:
        students = conn.execute(
            "SELECT student_index, title, name FROM students ORDER BY student_index"
        ).fetchall()

        if not students:
            raise RuntimeError("No students found in database. Process attendance sheets first.")

        sessions_raw = conn.execute(
            "SELECT DISTINCT session_id FROM attendance ORDER BY session_id"
        ).fetchall()

        session_ids = [s["session_id"] for s in sessions_raw]
        if not session_ids:
            raise RuntimeError("No attendance sessions found in database. Process attendance sheets first.")

        attendance_records = conn.execute(
            "SELECT student_index, session_id, present FROM attendance"
        ).fetchall()
    finally:
        conn.close()

    att_map = {(r["student_index"], r["session_id"]): r["present"] for r in attendance_records}

    n_students = len(students)
    n_sessions = len(session_ids)
    matrix = np.full((n_students, n_sessions), -1, dtype=int)

    student_summaries = []

    for i, s in enumerate(students):
        idx = s["student_index"]
        name = s["name"]
        title = s["title"] or ""

        present_cnt = 0
        absent_cnt = 0
        missing_cnt = 0

        for j, sess in enumerate(session_ids):
            val = att_map.get((idx, sess))
            if val is None:
                matrix[i, j] = -1
                missing_cnt += 1
            elif val == 1:
                matrix[i, j] = 1
                present_cnt += 1
            else:
                matrix[i, j] = 0
                absent_cnt += 1

        total_sessions = present_cnt + absent_cnt
        pct = (present_cnt / total_sessions * 100.0) if total_sessions > 0 else 0.0

        student_summaries.append(
            {
                "student_index": idx,
                "title": title,
                "name": name,
                "total_conducted": n_sessions,
                "total_attended": present_cnt,
                "total_absent": absent_cnt,
                "total_missing": missing_cnt,
                "percentage": round(pct, 2),
            }
        )

    # Export aggregated summary CSV
    csv_out = Path(out_csv_path)
    csv_out.parent.mkdir(parents=True, exist_ok=True)

    with csv_out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = [
            "student_index",
            "title",
            "name",
            "total_sessions",
            "sessions_attended",
            "sessions_absent",
            "sessions_missing",
            "attendance_percentage",
        ] + [f"session_{sess}" for sess in session_ids]
        writer.writerow(header)

        for i, s_sum in enumerate(student_summaries):
            sess_vals = []
            for j in range(n_sessions):
                v = matrix[i, j]
                if v == 1:
                    sess_vals.append("Present")
                elif v == 0:
                    sess_vals.append("Absent")
                else:
                    sess_vals.append("Missing")

            writer.writerow(
                [
                    s_sum["student_index"],
                    s_sum["title"],
                    s_sum["name"],
                    s_sum["total_conducted"],
                    s_sum["total_attended"],
                    s_sum["total_absent"],
                    s_sum["total_missing"],
                    f"{s_sum['percentage']:.2f}%",
                ]
                + sess_vals
            )

    print(f"Exported class summary CSV: {csv_out.resolve()}")

    # Generate Heatmap PNG Chart
    # Color mapping: -1 (Missing) -> Gray, 0 (Absent) -> Red, 1 (Present) -> Green
    cmap_colors = ["#9e9e9e", "#c62828", "#2e7d32"]
    display_matrix = matrix + 1  # maps [-1, 0, 1] to [0, 1, 2]

    fig_h = max(4.5, n_students * 0.6 + 2.0)
    fig_w = max(7.0, n_sessions * 1.2 + 4.0)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    cmap = ListedColormap(cmap_colors)
    ax.imshow(display_matrix, cmap=cmap, vmin=0, vmax=2, aspect="auto")

    ax.set_xticks(np.arange(n_sessions))
    ax.set_yticks(np.arange(n_students))

    ax.set_xticklabels(session_ids, rotation=35, ha="right", fontsize=9, fontweight="bold")

    y_labels = [
        f"{s['student_index']} - {s['name']} ({s['percentage']:.1f}%)" for s in student_summaries
    ]
    ax.set_yticklabels(y_labels, fontsize=9, fontweight="bold")

    for i in range(n_students):
        for j in range(n_sessions):
            val = matrix[i, j]
            if val == 1:
                text = "P"
                color = "white"
            elif val == 0:
                text = "A"
                color = "white"
            else:
                text = "-"
                color = "black"
            ax.text(j, i, text, ha="center", va="center", color=color, fontweight="bold", fontsize=10)

    ax.set_title("Class Attendance Dashboard (Student vs Session)", fontsize=13, fontweight="bold", pad=15)
    ax.set_xlabel("Sessions / Signing Sheets", fontsize=11, fontweight="bold", labelpad=10)
    ax.set_ylabel("Students & Overall Attendance (%)", fontsize=11, fontweight="bold", labelpad=10)

    legend_patches = [
        mpatches.Patch(color="#2e7d32", label="Present (P)"),
        mpatches.Patch(color="#c62828", label="Absent (A)"),
        mpatches.Patch(color="#9e9e9e", label="Missing (-)"),
    ]
    ax.legend(handles=legend_patches, bbox_to_anchor=(1.02, 1), loc="upper left", borderaxespad=0.0, frameon=True)

    fig.tight_layout()
    chart_out = Path(out_chart_path)
    chart_out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(chart_out, dpi=180, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved class dashboard chart: {chart_out.resolve()}\n")

    print("=" * 75)
    print("CLASS ATTENDANCE SUMMARY")
    print("=" * 75)
    print(f"{'Index':<10} {'Name':<32} {'Attended':<10} {'Percentage':<10}")
    print("-" * 75)
    for s in student_summaries:
        att_str = f"{s['total_attended']}/{s['total_conducted']}"
        print(f"{s['student_index']:<10} {s['name']:<32} {att_str:<10} {s['percentage']:>8.2f}%")
    print("=" * 75)

    return {
        "student_count": n_students,
        "session_count": n_sessions,
        "summaries": student_summaries,
        "csv_path": str(csv_out.resolve()),
        "chart_path": str(chart_out.resolve()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Class Attendance Dashboard & CSV Generator")
    parser.add_argument("--db", default="outputs/attendance.db", help="SQLite database path")
    parser.add_argument(
        "--out-chart",
        default="outputs/charts/class_attendance_dashboard.png",
        help="Output PNG chart path",
    )
    parser.add_argument(
        "--out-csv",
        default="outputs/class_attendance_summary.csv",
        help="Output summary CSV path",
    )
    args = parser.parse_args()

    generate_class_dashboard(
        db_path=args.db,
        out_chart_path=args.out_chart,
        out_csv_path=args.out_csv,
    )


if __name__ == "__main__":
    main()
