# OMRScan

> ## ⚠️ This project is in beta
> **It's in beta version.** Core scanning and grading work, but expect rough edges and occasional bugs.
> **More customizability and features are coming.** See the [roadmap](#roadmap).

A Python + OpenCV optical mark recognition (OMR) scanner with a Flask web interface.
Upload photos or scans of answer sheets, set an answer key, and get scores, chest numbers, company letters and an Excel report.
---

## Features

- Scan a single sheet or a whole folder of sheets at once
- 100-question sheets in four columns of 25, with A–D choices
- Reads a 3-digit chest number and a company letter (A–J)
- Answer key editor that mirrors the sheet layout, with type-or-paste entry
- Answer key is remembered in the browser between visits
- Automatic sheet detection and perspective correction
- Annotated result image, colour-coded answer map and per-question table
- Bulk results are searchable and sortable, with flags for unreadable or duplicate chest numbers
- Excel export with summary, per-question detail and answer key sheets
- Light and dark mode, works on mobile

## Current limitations (beta)

- **One fixed sheet layout.** Bubble positions are hard-coded for a single 100-question template. Sheets with a different layout will not read correctly until you re-measure the values in `OMRConfig` (see [Calibration](#calibrating-for-a-different-sheet)).
- Answer choices are A–D only, and the question count is fixed at 100.
- Photos with missing corners, heavy shadows or strong blur may misread. Flat, well-lit scans work best.
- No login or user accounts. Run it on a trusted machine or network.

## Roadmap

More customizability and features are coming. Planned and under consideration:

- [ ] Configurable layouts: question count, number of choices, columns and chest-number digits from the interface
- [ ] Layout templates and a calibration helper so new sheet designs don't need code edits
- [ ] Multiple answer keys / exam versions
- [ ] Partial credit and negative marking
- [ ] Manual correction of misread bubbles before export
- [ ] More export formats (CSV, PDF reports)
- [ ] Saved scan history

Ideas and bug reports are welcome. Please open an issue.

---

## Quick start

**Requirements:** Python 3.10–3.13 recommended. Newer Python versions may not have compatible OpenCV/NumPy builds yet.

```bash
git clone <https://github.com/Dev4vr4th/OMR-SCANNER-beta-version-.git>
cd <OMR-SCANNER-beta-version->
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5000** in your browser.

Options:

| Setting | Effect |
|---------|--------|
| `PORT=8080` | Run on a different port |
| `FLASK_DEBUG=1` | Enable Flask debug mode while developing |

For production use a real server, for example `gunicorn app:app`.

## How to use

1. Choose **One sheet** or **Many sheets** and add your image(s). Use *Download a sample sheet* to try it out.
2. Fill in the **answer key**: click bubbles, or type/paste something like `ABCDDCBA…` (use `-` to skip a question).
3. Click **Scan and grade**.
4. Review the score, annotated image and answer map. For batches, download the **Excel report**.

## Project layout

```
.
├── app.py                 Flask routes and Excel export
├── omr_engine.py          OpenCV pipeline and sheet geometry (OMRConfig)
├── requirements.txt       Python dependencies
├── templates/
│   └── index.html         Web interface (must stay inside templates/)
└── uploads/               Created automatically at runtime (temporary files)
```

> `index.html` has to live in a folder named `templates` next to `app.py`, otherwise Flask returns a `TemplateNotFound` error.

## How it works

```
Image → detect sheet edges → perspective warp to 850×1100
      → adaptive threshold → measure ink in each bubble
      → read chest no. / company / answers → compare to key → score + annotated image
```

## Calibrating for a different sheet

All positions live in `OMRConfig` at the top of `omr_engine.py`, in pixels on the warped 850×1100 canvas:

```python
NUM_QUESTIONS     = 100
QUESTIONS_PER_COL = 25
COLS = [{"ox": 94, "oy": 495}, ...]   # centre of the "A" bubble in row 1, per column
CHOICE_GAP    = 24                     # A → B → C → D spacing
ROW_GAP       = 22                     # spacing between rows
BUBBLE_RADIUS = 8

CHEST_COL_X / CHEST_ROW_Y              # chest-number digit bubbles
COMPANY_X0 / COMPANY_Y / COMPANY_GAP   # company bubbles A–J

FILL_FRAC   = 0.30                     # minimum ink fraction to count as marked
FILL_MARGIN = 0.08                     # winner must beat runner-up by this much
```

Download the sample sheet from the app and compare it with your own to check alignment.

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/scan_single` | POST | Form fields: `sheet` (image), `answer_key` (JSON array of 100 values, 0=A 1=B 2=C 3=D) |
| `/scan_bulk` | POST | Form fields: `sheets` (multiple images), `answer_key` |
| `/export_excel` | POST | JSON `{ "results": [...], "answer_key": [...] }`, returns an `.xlsx` file |
| `/sample_sheet` | GET | Downloads a PNG test sheet |

Example response from `/scan_single` (trimmed):

```json
{
  "filename": "sheet1.jpg",
  "student_id": "864",
  "company": "A",
  "sheet_detected": true,
  "score": 72,
  "total": 100,
  "score_pct": 72.0,
  "correct": 72,
  "wrong": 25,
  "blank": 3,
  "breakdown": [
    {"question": 1, "detected": "B", "correct": "B", "status": "correct"}
  ],
  "annotated_b64": "<base64 PNG>"
}
```

## Tips for best results

- Use even lighting and avoid shadows across the sheet
- Keep all four corners of the sheet visible in the photo
- Fill bubbles completely with a dark pen

## Contributing

This is an early beta, so feedback is especially useful. If something misreads, open an issue and include a sample image with any personal details removed.

## License

Released under the [MIT License](LICENSE). You are free to use, modify and share it, including commercially, as long as the license notice is kept.
