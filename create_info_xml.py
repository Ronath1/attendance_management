from __future__ import annotations

import argparse
import csv
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom


def prettify(root: ET.Element) -> str:
    raw = ET.tostring(root, encoding="utf-8")
    return minidom.parseString(raw).toprettyxml(indent="  ")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create info.xml from a CSV student list")
    parser.add_argument("csv_file", help="CSV with columns: index,title,name")
    parser.add_argument("--out", default="data/info.xml", help="Output XML path")
    parser.add_argument("--batch", default="sample", help="Batch/class id")
    parser.add_argument("--subject-code", default="CS402.3")
    parser.add_argument("--subject-title", default="Computer Graphics and Visualization")
    args = parser.parse_args()

    root = ET.Element("nsbm")
    subject = ET.SubElement(root, "subject")
    ET.SubElement(subject, "code").text = args.subject_code
    ET.SubElement(subject, "title").text = args.subject_title

    students_node = ET.SubElement(root, "students")
    batch_node = ET.SubElement(students_node, "batch", {"id": args.batch})

    with Path(args.csv_file).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"index", "title", "name"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"CSV is missing columns: {', '.join(sorted(missing))}")

        count = 0
        for row in reader:
            index = (row.get("index") or "").strip()
            name = (row.get("name") or "").strip()
            title = (row.get("title") or "").strip()
            if not index or not name:
                continue
            student = ET.SubElement(batch_node, "student")
            ET.SubElement(student, "index").text = index
            ET.SubElement(student, "title").text = title
            ET.SubElement(student, "name").text = name
            count += 1

    if count == 0:
        raise SystemExit("No valid students found in the CSV.")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(prettify(root), encoding="utf-8")
    print(f"Created {out.resolve()} with {count} students.")


if __name__ == "__main__":
    main()
