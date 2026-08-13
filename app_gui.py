from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from attendance.database import connect, save_attendance, upsert_students
from attendance.processor import estimate_student_rows, extract_students_from_sheet, process_sheet, session_id_from_image
from attendance.students import Student, load_students, placeholder_students, save_students_xml


SAMPLE_STUDENTS = [
    Student("10000409", "Ms", "M S Dilshanika Perera"),
    Student("10009301", "Mr", "C W M A Shehan Abeyrathne"),
    Student("10009302", "Mr", "B A K M Chithrananda"),
    Student("10009303", "Ms", "W Shashini Minosha De Silva"),
    Student("10009304", "Mr", "K L Udara Maduranga Liyanage"),
    Student("10009306", "Mr", "Hansa Anuradha Wickramanayake"),
]


class AttendanceApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("CS402.3 Attendance Processor")
        self.geometry("980x620")
        self.minsize(860, 520)

        self.image_path = tk.StringVar()
        self.xml_path = tk.StringVar(value=str(Path("data/info.xml")))
        self.use_xml = tk.BooleanVar(value=True)
        self.use_ocr = tk.BooleanVar(value=True)
        self.row_count = tk.IntVar(value=6)
        self.db_path = tk.StringVar(value=str(Path("outputs/attendance.db")))
        self.status = tk.StringVar(value="Select a signing-sheet image. Use XML for names, or image-only mode for row results.")

        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        controls = ttk.LabelFrame(root, text="Inputs", padding=12)
        controls.pack(fill="x")

        self._path_row(controls, "Signing sheet", self.image_path, self._choose_image, 0)
        self._path_row(controls, "info.xml", self.xml_path, self._choose_xml, 1)

        mode_row = ttk.Frame(controls)
        mode_row.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        ttk.Checkbutton(mode_row, text="Use info.xml for student names", variable=self.use_xml).pack(side="left")
        ttk.Checkbutton(mode_row, text="Read table text from image", variable=self.use_ocr).pack(side="left", padx=(18, 0))
        ttk.Label(mode_row, text="Student rows if no XML:").pack(side="left", padx=(18, 6))
        ttk.Spinbox(mode_row, from_=1, to=200, textvariable=self.row_count, width=6).pack(side="left")

        actions = ttk.Frame(controls)
        actions.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        ttk.Button(actions, text="Process Sheet", command=self._process).pack(side="left")
        ttk.Button(actions, text="Configure XML", command=self._configure_xml).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Generate Sample Sheet", command=self._make_sample).pack(side="left", padx=8)
        ttk.Button(actions, text="Open Debug Folder", command=self._open_debug).pack(side="left")

        columns = ("index", "title", "name", "status", "ink_ratio")
        self.table = ttk.Treeview(root, columns=columns, show="headings", height=14)
        self.table.heading("index", text="Student No")
        self.table.heading("title", text="Title")
        self.table.heading("name", text="Student Name")
        self.table.heading("status", text="Status")
        self.table.heading("ink_ratio", text="Ink Ratio")
        self.table.column("index", width=120, anchor="center")
        self.table.column("title", width=70, anchor="center")
        self.table.column("name", width=430)
        self.table.column("status", width=130, anchor="center")
        self.table.column("ink_ratio", width=120, anchor="center")
        self.table.pack(fill="both", expand=True, pady=14)

        chart_bar = ttk.Frame(root)
        chart_bar.pack(fill="x")
        ttk.Label(chart_bar, text="Student index for chart:").pack(side="left")
        self.chart_index = tk.StringVar(value="001")
        ttk.Entry(chart_bar, textvariable=self.chart_index, width=16).pack(side="left", padx=8)
        ttk.Button(chart_bar, text="Create Chart", command=self._chart).pack(side="left")

        ttk.Label(root, textvariable=self.status).pack(fill="x", pady=(12, 0))

        controls.columnconfigure(1, weight=1)

    def _path_row(self, parent: ttk.Frame, label: str, variable: tk.StringVar, command, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=8, pady=4)
        ttk.Button(parent, text="Browse", command=command).grid(row=row, column=2, pady=4)

    def _choose_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Select signing-sheet image",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.image_path.set(path)
            try:
                rows = estimate_student_rows(path)
                if rows > 0:
                    self.row_count.set(rows)
                    self.status.set(f"Selected {Path(path).name}. Auto-detected {rows} student rows.")
            except Exception:
                self.status.set(f"Selected {Path(path).name}. Enter the student row count manually.")

    def _choose_xml(self) -> None:
        path = filedialog.askopenfilename(
            title="Select info.xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
        )
        if path:
            self.xml_path.set(path)

    def _configure_xml(self) -> None:
        XmlBuilder(self, self.xml_path)

    def _process(self) -> None:
        image = self.image_path.get().strip()
        xml = self.xml_path.get().strip()
        if not image:
            messagebox.showwarning("Missing image", "Please select a signing-sheet image.")
            return

        try:
            if self.use_xml.get():
                if not xml:
                    messagebox.showwarning("Missing XML", "Please select an info.xml file or turn off XML mode.")
                    return
                students = load_students(xml)
            else:
                if self.use_ocr.get():
                    students = extract_students_from_sheet(image, int(self.row_count.get()))
                else:
                    students = placeholder_students(int(self.row_count.get()))
            session_id = session_id_from_image(image)
            debug_dir = "outputs/debug"
            if not self.use_xml.get():
                session_id = f"{session_id}_rows_only"
                debug_dir = str(Path(debug_dir) / session_id)
            results, _ = process_sheet(image, students, debug_dir=debug_dir)
            rows = [
                {
                    "session_id": session_id,
                    "image_file": str(Path(image).resolve()),
                    "student_index": r.student.index,
                    "present": int(r.present),
                    "ink_pixels": r.ink_pixels,
                    "ink_ratio": r.ink_ratio,
                    "confidence": r.confidence,
                }
                for r in results
            ]

            conn = connect(self.db_path.get())
            upsert_students(conn, students)
            save_attendance(conn, rows)

            for item in self.table.get_children():
                self.table.delete(item)
            for result in results:
                status = "Present" if result.present else "Absent"
                self.table.insert(
                    "",
                    "end",
                    values=(result.student.index, result.student.title, result.student.name, status, f"{result.ink_ratio:.4f}"),
                )

            if results:
                self.chart_index.set(results[0].student.index)
            if self.use_xml.get():
                label_mode = "XML names"
            elif self.use_ocr.get():
                label_mode = "OCR text from image"
            else:
                label_mode = "image-only row labels"
            self.status.set(f"Processed {Path(image).name} using {label_mode}. Debug images saved in {Path(debug_dir).resolve() / Path(image).stem}.")
        except Exception as exc:
            messagebox.showerror("Processing failed", str(exc))

    def _chart(self) -> None:
        index = self.chart_index.get().strip()
        if not index:
            messagebox.showwarning("Missing index", "Enter a student index first.")
            return
        try:
            import infovis

            old_argv = __import__("sys").argv
            __import__("sys").argv = ["infovis.py", index, "--db", self.db_path.get()]
            try:
                infovis.main()
            finally:
                __import__("sys").argv = old_argv
            self.status.set(f"Chart saved in outputs/charts/{index}_attendance.png.")
        except Exception as exc:
            messagebox.showerror("Chart failed", str(exc))

    def _make_sample(self) -> None:
        try:
            import make_sample_sheet

            make_sample_sheet.main()
            self.image_path.set(str(Path("data/sample_sheet.png")))
            self.xml_path.set(str(Path("data/info.xml")))
            self.use_xml.set(True)
            self.row_count.set(3)
            self.status.set("Sample sheet generated. Click Process Sheet to test it.")
        except Exception as exc:
            messagebox.showerror("Sample generation failed", str(exc))

    def _open_debug(self) -> None:
        path = Path("outputs/debug").resolve()
        path.mkdir(parents=True, exist_ok=True)
        import os

        os.startfile(path)


class XmlBuilder(tk.Toplevel):
    def __init__(self, parent: AttendanceApp, xml_path_var: tk.StringVar) -> None:
        super().__init__(parent)
        self.title("Configure info.xml")
        self.geometry("820x540")
        self.minsize(720, 460)
        self.xml_path_var = xml_path_var
        self.batch_id = tk.StringVar(value="configured")
        self.subject_code = tk.StringVar(value="CS402.3")
        self.subject_title = tk.StringVar(value="Computer Graphics and Visualization")
        self.editing_item: str | None = None

        self._build_ui()
        current = Path(self.xml_path_var.get())
        if current.exists():
            self._load_from_path(current)
        else:
            self._prefill_sample()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        meta = ttk.LabelFrame(root, text="XML Details", padding=10)
        meta.pack(fill="x")
        ttk.Label(meta, text="Batch").grid(row=0, column=0, sticky="w")
        ttk.Entry(meta, textvariable=self.batch_id, width=18).grid(row=0, column=1, sticky="w", padx=(6, 18))
        ttk.Label(meta, text="Subject Code").grid(row=0, column=2, sticky="w")
        ttk.Entry(meta, textvariable=self.subject_code, width=18).grid(row=0, column=3, sticky="w", padx=(6, 18))
        ttk.Label(meta, text="Subject Title").grid(row=0, column=4, sticky="w")
        ttk.Entry(meta, textvariable=self.subject_title).grid(row=0, column=5, sticky="ew", padx=(6, 0))
        meta.columnconfigure(5, weight=1)

        form = ttk.LabelFrame(root, text="Student", padding=10)
        form.pack(fill="x", pady=(10, 0))
        self.index_var = tk.StringVar()
        self.title_var = tk.StringVar(value="Mr")
        self.name_var = tk.StringVar()
        ttk.Label(form, text="Student No").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.index_var, width=18).grid(row=0, column=1, padx=(6, 12))
        ttk.Label(form, text="Title").grid(row=0, column=2, sticky="w")
        ttk.Combobox(form, textvariable=self.title_var, values=("Mr", "Ms", "Mrs", "Dr"), width=8).grid(row=0, column=3, padx=(6, 12))
        ttk.Label(form, text="Student Name").grid(row=0, column=4, sticky="w")
        ttk.Entry(form, textvariable=self.name_var).grid(row=0, column=5, sticky="ew", padx=(6, 0))
        form.columnconfigure(5, weight=1)

        form_actions = ttk.Frame(form)
        form_actions.grid(row=1, column=0, columnspan=6, sticky="w", pady=(10, 0))
        ttk.Button(form_actions, text="Add / Update Row", command=self._add_or_update).pack(side="left")
        ttk.Button(form_actions, text="Clear Fields", command=self._clear_fields).pack(side="left", padx=8)

        columns = ("index", "title", "name")
        self.table = ttk.Treeview(root, columns=columns, show="headings", height=12)
        self.table.heading("index", text="Student No")
        self.table.heading("title", text="Title")
        self.table.heading("name", text="Student Name")
        self.table.column("index", width=140, anchor="center")
        self.table.column("title", width=80, anchor="center")
        self.table.column("name", width=480)
        self.table.pack(fill="both", expand=True, pady=10)
        self.table.bind("<<TreeviewSelect>>", self._select_row)

        actions = ttk.Frame(root)
        actions.pack(fill="x")
        ttk.Button(actions, text="Remove Selected", command=self._remove_selected).pack(side="left")
        ttk.Button(actions, text="Move Up", command=lambda: self._move(-1)).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Move Down", command=lambda: self._move(1)).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Load XML", command=self._load_xml).pack(side="left", padx=(18, 0))
        ttk.Button(actions, text="Prefill 6 Sample Students", command=self._prefill_sample).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Save XML", command=self._save_xml).pack(side="right")

    def _students(self) -> list[Student]:
        students: list[Student] = []
        for item in self.table.get_children():
            index, title, name = self.table.item(item, "values")
            students.append(Student(str(index), str(title), str(name)))
        return students

    def _add_or_update(self) -> None:
        index = self.index_var.get().strip()
        title = self.title_var.get().strip()
        name = self.name_var.get().strip()
        if not index or not name:
            messagebox.showwarning("Missing student", "Student No and Student Name are required.", parent=self)
            return

        values = (index, title, name)
        if self.editing_item and self.table.exists(self.editing_item):
            self.table.item(self.editing_item, values=values)
        else:
            self.table.insert("", "end", values=values)
        self._clear_fields()

    def _clear_fields(self) -> None:
        self.editing_item = None
        self.index_var.set("")
        self.title_var.set("Mr")
        self.name_var.set("")
        self.table.selection_remove(self.table.selection())

    def _select_row(self, _event=None) -> None:
        selected = self.table.selection()
        if not selected:
            return
        self.editing_item = selected[0]
        index, title, name = self.table.item(self.editing_item, "values")
        self.index_var.set(index)
        self.title_var.set(title)
        self.name_var.set(name)

    def _remove_selected(self) -> None:
        for item in self.table.selection():
            self.table.delete(item)
        self._clear_fields()

    def _move(self, direction: int) -> None:
        selected = self.table.selection()
        if not selected:
            return
        item = selected[0]
        index = self.table.index(item)
        new_index = index + direction
        if 0 <= new_index < len(self.table.get_children()):
            self.table.move(item, "", new_index)

    def _prefill_sample(self) -> None:
        for item in self.table.get_children():
            self.table.delete(item)
        for student in SAMPLE_STUDENTS:
            self.table.insert("", "end", values=(student.index, student.title, student.name))
        self.batch_id.set("2016.1")
        self._clear_fields()

    def _load_from_path(self, path: Path) -> None:
        try:
            students = load_students(path)
        except Exception as exc:
            messagebox.showerror("Load failed", str(exc), parent=self)
            return
        for item in self.table.get_children():
            self.table.delete(item)
        for student in students:
            self.table.insert("", "end", values=(student.index, student.title, student.name))
        self._clear_fields()

    def _load_xml(self) -> None:
        path = filedialog.askopenfilename(
            title="Load info.xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
            parent=self,
        )
        if path:
            self.xml_path_var.set(path)
            self._load_from_path(Path(path))

    def _save_xml(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save info.xml",
            initialfile="info.xml",
            defaultextension=".xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
            parent=self,
        )
        if not path:
            return
        try:
            save_students_xml(
                path,
                self._students(),
                batch_id=self.batch_id.get().strip() or "configured",
                subject_code=self.subject_code.get().strip() or "CS402.3",
                subject_title=self.subject_title.get().strip() or "Computer Graphics and Visualization",
            )
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc), parent=self)
            return
        self.xml_path_var.set(path)
        messagebox.showinfo("Saved", f"Saved XML:\n{path}", parent=self)
        self.destroy()


if __name__ == "__main__":
    AttendanceApp().mainloop()
