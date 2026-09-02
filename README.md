# CS402.3 Student Attendance Management Prototype

This prototype processes signing-sheet photos, detects signatures in the student signature column, stores attendance in SQLite, and creates student attendance charts and class-wide dashboards.

## Installation & Setup

1. **Python Prerequisites**: Ensure Python 3.9+ is installed.
2. **Install Required Libraries**:
   ```powershell
   pip install opencv-python pytesseract matplotlib numpy
   ```
3. **OCR Engine (Optional for OCR mode)**:
   Install Tesseract-OCR on your system if using automatic sheet text extraction.

## Single Sheet Processing

```powershell
python make_sample_sheet.py
python sams.py data\sample_sheet.png data\info.xml
python infovis.py 001
python investigate.py 001
```

## Easier GUI demo

Run this if you want buttons for selecting the image and XML file:

```powershell
python app_gui.py
```

Then:

1. Click `Generate Sample Sheet`, or browse to a real signing-sheet image.
2. Click `Configure XML` to create or edit the student list inside the app.
3. Click `Process Sheet`.
4. Read the present/absent table.
5. Click `Create Chart` to save a student graph.

For best accuracy, keep `Use info.xml for student names` ticked after saving XML. OCR mode is convenient, but phone photos can make names and numbers imperfect.

## Create info.xml from CSV

Make a CSV file with these columns:

```csv
index,title,name
001,Mr,John Snow
007,Mr,James Bond
009,Mr,Andare
```

Then run:

```powershell
python create_info_xml.py students.csv --out data\info.xml
```

Process your real coursework sheets after you receive them:

```powershell
python sams.py "path\to\your_sheet.png" data\info.xml --csv "outputs\sheet_result.csv"
```

Image-only mode:

```powershell
python sams.py "path\to\your_sheet.png"
```

The program will try to auto-detect the number of student rows. If it gets the count wrong, provide the row count manually:

```powershell
python sams.py "path\to\your_sheet.png" --rows 30
```

Image-only mode labels students as `ROW001`, `ROW002`, etc. Use XML when you need real names and index numbers.

## Batch Signing-Sheet Processing

To process an entire folder containing multiple signing-sheet photos (`.png`, `.jpg`, `.jpeg`):

```powershell
python batch_sams.py "path\to\image_folder" data\info.xml
```

Key features of batch processing:
- Processes images in alphabetical order.
- Generates a unique session ID for every signing-sheet image.
- Stores attendance records into `outputs/attendance.db`.
- Error tolerance: Continues processing remaining images if one file fails or is corrupted, logging a clear error.
- Displays live progress (`[1/N]`) and prints a final batch summary table.

Options:
- `--db outputs/custom.db`: Specify a custom SQLite database path.
- `--threshold 0.03`: Adjust ink ratio detection sensitivity threshold.
- `--debug-dir outputs/debug`: Output directory for processing debug screenshots.

Example Output:
```text
Found 3 signing-sheet image(s) in 'c:\attendance\images'.

[1/3] Processing image: lecture_01.png...
   --> Success: 2/3 present. Session ID: lecture_01

[2/3] Processing image: lecture_02.jpg...
   --> Success: 1/3 present. Session ID: lecture_02

[3/3] Processing image: corrupt_photo.jpg...
   --> ERROR processing 'corrupt_photo.jpg': Could not read image

========================================================================
BATCH PROCESSING FINAL SUMMARY
========================================================================
Total Images Discovered : 3
Successfully Processed : 2
Failed / Skipped      : 1
------------------------------------------------------------------------
Filename                       Status     Details
------------------------------------------------------------------------
lecture_01.png                 SUCCESS    2/3 Present (Session: lecture_01)
lecture_02.jpg                 SUCCESS    1/3 Present (Session: lecture_02)
corrupt_photo.jpg              FAILED     Could not read image
========================================================================
```

## Class Attendance Dashboard & Aggregated CSV

Generate a overall class attendance heatmap and export class summary metrics across all processed sessions:

```powershell
python class_dashboard.py
```

Output Artifacts:
- **PNG Heatmap Chart**: `outputs/charts/class_attendance_dashboard.png`
  - Green cells: **Present (P)**
  - Red cells: **Absent (A)**
  - Gray cells: **Missing/No Record (-)**
  - Y-axis includes student index, student name, and overall attendance percentage.
- **Aggregated CSV**: `outputs/class_attendance_summary.csv`
  - Contains student index, title, name, total sessions, sessions attended, sessions absent, missing sessions, overall attendance percentage, and session-by-session columns.

Options:
- `--db outputs/attendance.db`: SQLite database source.
- `--out-chart outputs/charts/custom_dashboard.png`: Custom output PNG path.
- `--out-csv outputs/custom_summary.csv`: Custom output CSV path.

## Running Automated Tests

Run the unit test suite covering batch processing, error handling, database storage, and dashboard generation:

```powershell
python -m unittest discover tests
```

To compile and verify Python syntax across all project files:
```powershell
python -m py_compile batch_sams.py class_dashboard.py sams.py app_gui.py infovis.py investigate.py create_info_xml.py make_sample_sheet.py attendance/*.py tests/*.py
```

## Contribution – G.M.A.M. Bandara (28445)

This section describes the specific individual work contributed by G.M.A.M. Bandara (Student Index 28445) to the Student Attendance Management System project:

1. **Batch Signing-Sheet Processing Engine (`batch_sams.py`)**:
   - Developed batch directory scanning with case-insensitive image file filtering (`.png`, `.jpg`, `.jpeg`) and deterministic sorted ordering.
   - Built robust session ID generator and database integration to automatically insert/upsert batch results into SQLite.
   - Implemented error-tolerant exception handling so invalid or corrupt files do not halt batch execution.
   - Designed live execution progress reporting and a comprehensive terminal batch summary.

2. **Class Attendance Dashboard & CSV Summary (`class_dashboard.py`)**:
   - Implemented multi-session database aggregation logic to compute per-student attendance totals and percentages.
   - Created a 2D class attendance matrix representation covering Present, Absent, and Missing states.
   - Designed a visualization heatmap using `matplotlib` with custom color coding (Green = Present, Red = Absent, Gray = Missing) and annotated cell markers.
   - Built automated CSV export functionality (`class_attendance_summary.csv`) providing detailed per-session metrics for academic reporting.

3. **Automated Testing & Quality Assurance (`tests/test_batch_workflow.py`)**:
   - Created comprehensive automated unit tests using isolated temporary file system environments and test databases.
   - Implemented test cases validating valid batch execution, database persistence, corrupted file fault tolerance, and summary dashboard calculations.

## Files

- `sams.py` - main image processing and attendance storage program.
- `batch_sams.py` - batch signing-sheet processing script for multiple images.
- `class_dashboard.py` - class-wide attendance heatmap dashboard and CSV summary export.
- `app_gui.py` - desktop GUI for selecting an image/XML and viewing results.
- `infovis.py` - attendance visualization for one student.
- `investigate.py` - simple signature consistency investigation.
- `make_sample_sheet.py` - creates a synthetic test sheet, useful before real campus images are available.
- `create_info_xml.py` - converts a CSV student list into `info.xml`.
- `attendance/processor.py` - OpenCV table/signature detector.
- `attendance/database.py` - SQLite connection and query helper functions.
- `attendance/students.py` - Student data structure and XML loading/saving functions.
- `tests/test_batch_workflow.py` - automated unit tests for batch processing and dashboard export.
- `data/info.xml` - sample student list based on the provided signing sheets.
- `outputs/attendance.db` - generated SQLite database.
- `outputs/class_attendance_summary.csv` - exported class attendance summary.
- `outputs/debug/` - generated processing screenshots for the report.
- `outputs/charts/` - generated graphs and class dashboard heatmaps.

## Method

The detector uses the static signing-sheet layout:

1. Convert image to grayscale.
2. Binarize the image.
3. Detect horizontal and vertical table lines.
4. Locate the student table and the final signature column.
5. Crop each student's signature cell.
6. Detect blue/dark ink pixels.
7. Mark the student present if the ink ratio passes a threshold.

The generated debug images and class dashboard heatmap can be used directly in the coursework report to show the processing pipeline and aggregate attendance results.
