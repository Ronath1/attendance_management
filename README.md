# CS402.3 Student Attendance Management Prototype

This prototype processes signing-sheet photos, detects signatures in the student signature column, stores attendance in SQLite, and creates student attendance charts.

## Run

```powershell
cd prototype
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

## Files

- `sams.py` - main image processing and attendance storage program.
- `app_gui.py` - simple desktop GUI for selecting an image/XML and viewing results.
- `infovis.py` - attendance visualization for one student.
- `investigate.py` - simple signature consistency investigation.
- `make_sample_sheet.py` - creates a synthetic test sheet, useful before real campus images are available.
- `create_info_xml.py` - converts a CSV student list into `info.xml`.
- `attendance/processor.py` - OpenCV table/signature detector.
- `data/info.xml` - sample student list based on the provided signing sheets.
- `outputs/attendance.db` - generated SQLite database.
- `outputs/debug/` - generated processing screenshots for the report.
- `outputs/charts/` - generated graphs for the report.

## Method

The detector uses the static signing-sheet layout:

1. Convert image to grayscale.
2. Binarize the image.
3. Detect horizontal and vertical table lines.
4. Locate the student table and the final signature column.
5. Crop each student's signature cell.
6. Detect blue/dark ink pixels.
7. Mark the student present if the ink ratio passes a threshold.

The generated debug images can be used directly in the coursework report to show the processing pipeline.
