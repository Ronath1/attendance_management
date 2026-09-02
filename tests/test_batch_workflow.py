from __future__ import annotations

import csv
import os
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from attendance.database import connect, summary
from attendance.students import Student, save_students_xml
from batch_sams import process_batch
from class_dashboard import generate_class_dashboard


class TestBatchWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        self.img_dir = self.root / "images"
        self.img_dir.mkdir()

        self.xml_path = self.root / "info.xml"
        self.db_path = self.root / "test_attendance.db"
        self.debug_dir = self.root / "debug"
        self.chart_path = self.root / "dashboard.png"
        self.csv_path = self.root / "summary.csv"

        self.students = [
            Student("001", "Mr", "John Snow"),
            Student("007", "Mr", "James Bond"),
            Student("009", "Mr", "Andare"),
        ]
        save_students_xml(self.xml_path, self.students)

        self.valid_img_1 = self.img_dir / "sheet_01.png"
        self.valid_img_2 = self.img_dir / "sheet_02.jpg"
        self.corrupt_img = self.img_dir / "sheet_corrupt.png"

        self._create_dummy_sheet(self.valid_img_1, signed_indices=[0, 1])
        self._create_dummy_sheet(self.valid_img_2, signed_indices=[0])
        self.corrupt_img.write_text("CORRUPTED_NON_IMAGE_DATA", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_dummy_sheet(self, path: Path, signed_indices: list[int]):
        width, height = 1200, 850
        image = np.full((height, width, 3), 255, dtype=np.uint8)

        x0, y0 = 90, 330
        col_widths = [90, 190, 90, 455, 220]
        row_h = 58
        rows = len(self.students) + 1
        table_w = sum(col_widths)
        table_h = rows * row_h

        xs = [x0]
        for w in col_widths:
            xs.append(xs[-1] + w)

        for x in xs:
            cv2.line(image, (x, y0), (x, y0 + table_h), (20, 20, 20), 2)
        for y in range(y0, y0 + table_h + 1, row_h):
            cv2.line(image, (x0, y), (x0 + table_w, y), (20, 20, 20), 2)

        for row, student in enumerate(self.students, start=1):
            y_text = y0 + row * row_h + 37
            cv2.putText(image, str(row), (xs[0] + 18, y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (30, 30, 30), 2)
            cv2.putText(image, student.index, (xs[1] + 18, y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (30, 30, 30), 2)
            cv2.putText(image, student.title, (xs[2] + 18, y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (30, 30, 30), 2)
            cv2.putText(image, student.name, (xs[3] + 18, y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (30, 30, 30), 2)

        blue = (180, 55, 20)
        for idx in signed_indices:
            row = idx + 1
            cv2.line(image, (xs[-2] + 30, y0 + row * row_h + 30), (xs[-1] - 30, y0 + row * row_h + 30), blue, 4)

        cv2.imwrite(str(path), image)

    def test_batch_processing_and_error_handling(self):
        res = process_batch(
            folder_path=self.img_dir,
            info_xml_path=self.xml_path,
            db_path=self.db_path,
            debug_dir=self.debug_dir,
        )

        self.assertEqual(res["total"], 3)
        self.assertEqual(res["success"], 2)
        self.assertEqual(res["failed"], 1)

        conn = connect(self.db_path)
        try:
            sums = {r["student_index"]: r for r in summary(conn)}
        finally:
            conn.close()

        self.assertIn("001", sums)
        self.assertEqual(sums["001"]["present_count"], 2)
        self.assertEqual(sums["001"]["sessions"], 2)
        self.assertEqual(sums["001"]["percentage"], 100.0)

        self.assertIn("007", sums)
        self.assertEqual(sums["007"]["present_count"], 1)
        self.assertEqual(sums["007"]["sessions"], 2)
        self.assertEqual(sums["007"]["percentage"], 50.0)

        self.assertIn("009", sums)
        self.assertEqual(sums["009"]["present_count"], 0)
        self.assertEqual(sums["009"]["sessions"], 2)
        self.assertEqual(sums["009"]["percentage"], 0.0)

    def test_class_dashboard_and_csv_export(self):
        process_batch(
            folder_path=self.img_dir,
            info_xml_path=self.xml_path,
            db_path=self.db_path,
            debug_dir=self.debug_dir,
        )

        dash_res = generate_class_dashboard(
            db_path=self.db_path,
            out_chart_path=self.chart_path,
            out_csv_path=self.csv_path,
        )

        self.assertEqual(dash_res["student_count"], 3)
        self.assertEqual(dash_res["session_count"], 2)

        self.assertTrue(self.chart_path.exists())
        self.assertGreater(os.path.getsize(self.chart_path), 1000)

        self.assertTrue(self.csv_path.exists())
        with self.csv_path.open(encoding="utf-8") as f:
            reader = list(csv.reader(f))
            self.assertEqual(len(reader), 4)


if __name__ == "__main__":
    unittest.main()
