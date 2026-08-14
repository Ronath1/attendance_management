from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from attendance.students import load_students


def main() -> None:
    students = load_students("data/info.xml")
    out = Path("data/sample_sheet.png")
    out.parent.mkdir(parents=True, exist_ok=True)

    width, height = 1200, 850
    image = np.full((height, width, 3), 255, dtype=np.uint8)

    cv2.putText(image, "Signing Sheet", (90, 105), cv2.FONT_HERSHEY_SIMPLEX, 1.35, (35, 35, 35), 3)
    cv2.putText(image, "NSBM Green University Town", (90, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (45, 45, 45), 2)
    cv2.putText(image, "School of Computing", (90, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (45, 45, 45), 2)
    cv2.putText(image, "BSc (Hons) in Software Engineering - 2016.1", (90, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (45, 45, 45), 2)

    x0, y0 = 90, 330
    col_widths = [90, 190, 90, 455, 220]
    row_h = 58
    rows = len(students) + 1
    table_w = sum(col_widths)
    table_h = rows * row_h

    xs = [x0]
    for w in col_widths:
        xs.append(xs[-1] + w)
    ys = [y0 + i * row_h for i in range(rows + 1)]

    for x in xs:
        cv2.line(image, (x, y0), (x, y0 + table_h), (20, 20, 20), 2)
    for y in ys:
        cv2.line(image, (x0, y), (x0 + table_w, y), (20, 20, 20), 2)

    headers = ["No", "Student Index", "Title", "Student Name", "Signature"]
    for i, header in enumerate(headers):
        cv2.putText(image, header, (xs[i] + 15, y0 + 38), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (25, 25, 25), 2)

    for row, student in enumerate(students, start=1):
        y_text = y0 + row * row_h + 37
        values = [str(row), student.index, student.title, student.name]
        for i, value in enumerate(values):
            cv2.putText(image, value, (xs[i] + 18, y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (30, 30, 30), 2)

    # Two present students and one absent student, matching the coursework example.
    blue = (180, 55, 20)
    cv2.line(image, (xs[-2] + 35, y0 + row_h + 34), (xs[-1] - 60, y0 + row_h + 20), blue, 3)
    cv2.line(image, (xs[-2] + 60, y0 + row_h + 20), (xs[-1] - 35, y0 + row_h + 40), blue, 3)
    cv2.putText(image, "JamesBond007", (xs[-2] + 18, y0 + 2 * row_h + 39), cv2.FONT_HERSHEY_SIMPLEX, 0.48, blue, 2)

    cv2.imwrite(str(out), image)
    print(f"Sample sheet written: {out.resolve()}")


if __name__ == "__main__":
    main()
