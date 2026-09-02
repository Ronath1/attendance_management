from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom


@dataclass
class Student:
    index: str
    title: str
    name: str


def load_students(xml_path: str | Path) -> list[Student]:
    xml_path = Path(xml_path)
    if not xml_path.exists():
        raise FileNotFoundError(f"XML file not found: {xml_path}")

    tree = ET.parse(xml_path)
    root = tree.getroot()
    students: list[Student] = []

    for student_elem in root.iter("student"):
        index_elem = student_elem.find("index")
        title_elem = student_elem.find("title")
        name_elem = student_elem.find("name")

        index = index_elem.text.strip() if index_elem is not None and index_elem.text else ""
        title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
        name = name_elem.text.strip() if name_elem is not None and name_elem.text else ""

        if index or name:
            students.append(Student(index=index, title=title, name=name))

    return students


def placeholder_students(count: int) -> list[Student]:
    return [
        Student(index=f"ROW{i + 1:03d}", title="", name=f"Student Row {i + 1}")
        for i in range(count)
    ]


def save_students_xml(
    xml_path: str | Path,
    students: list[Student],
    batch_id: str = "sample",
    subject_code: str = "CS402.3",
    subject_title: str = "Computer Graphics and Visualization",
) -> None:
    root = ET.Element("nsbm")
    subject = ET.SubElement(root, "subject")
    ET.SubElement(subject, "code").text = subject_code
    ET.SubElement(subject, "title").text = subject_title

    students_node = ET.SubElement(root, "students")
    batch_node = ET.SubElement(students_node, "batch", {"id": batch_id})

    for s in students:
        student_node = ET.SubElement(batch_node, "student")
        ET.SubElement(student_node, "index").text = s.index
        ET.SubElement(student_node, "title").text = s.title
        ET.SubElement(student_node, "name").text = s.name

    raw = ET.tostring(root, encoding="utf-8")
    pretty = minidom.parseString(raw).toprettyxml(indent="  ")

    out = Path(xml_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pretty, encoding="utf-8")
