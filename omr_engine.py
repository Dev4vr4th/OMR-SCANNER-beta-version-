"""
OMR Engine - 100-question sheet reader
All coordinates are pixel-measured from the sheet warped to an 850x1100 canvas.

Answer grid : 4 cols x 25 rows = 100 questions
Chest No    : 3 digit cols, digits 0-9
              col x = [93, 117, 141]
              row y = [174,195,217,239,261,283,305,327,349,371]
Company     : 10 bubbles A-J, y=261, x0=439, gap=24
"""

import cv2
import numpy as np


class OMRConfig:
    CANVAS_W = 850
    CANVAS_H = 1100

    NUM_QUESTIONS     = 100
    NUM_CHOICES       = 4
    CHOICE_LABELS     = ["A", "B", "C", "D"]
    QUESTIONS_PER_COL = 25

    # 4 answer columns - ox = centre of A bubble, oy = centre of row 1
    # All measured from the warped sheet
    COLS = [
        {"ox": 94,  "oy": 495},   # Q1-Q25
        {"ox": 304, "oy": 495},   # Q26-Q50
        {"ox": 508, "oy": 495},   # Q51-Q75
        {"ox": 711, "oy": 495},   # Q76-Q100
    ]
    CHOICE_GAP    = 24   # horizontal px A->B->C->D (measured: consistent 24px)
    ROW_GAP       = 22   # vertical px between rows (measured: exactly 22px)
    BUBBLE_RADIUS = 8

    # Chest No - 3 digit columns
    # Exact x centres: 93, 117, 141
    # Exact y per digit (0-9): measured individually (gap not perfectly uniform)
    CHEST_DIGITS     = 3
    CHEST_DIGIT_VALS = 10
    CHEST_COL_X      = [93, 117, 141]
    CHEST_ROW_Y      = [174, 195, 217, 239, 261, 283, 305, 327, 349, 371]
    CHEST_BUBBLE_R   = 8

    # Company - 10 bubbles A-J
    # Measured: y=261, first bubble x=439, gap=24px
    COMPANY_LABELS   = list("ABCDEFGHIJ")
    COMPANY_Y        = 261
    COMPANY_X0       = 439
    COMPANY_GAP      = 24
    COMPANY_BUBBLE_R = 10

    # Fill detection
    FILL_FRAC   = 0.30
    FILL_MARGIN = 0.08


# ─── Geometry ─────────────────────────────────────────────────────────────────

def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s    = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)];  rect[2] = pts[np.argmax(s)]
    diff    = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]; rect[3] = pts[np.argmax(diff)]
    return rect


def four_point_transform(image, pts):
    rect = order_points(pts)
    tl, tr, br, bl = rect
    maxW = max(int(np.linalg.norm(br - bl)), int(np.linalg.norm(tr - tl)))
    maxH = max(int(np.linalg.norm(tr - br)), int(np.linalg.norm(tl - bl)))
    dst  = np.array([[0,0],[maxW-1,0],[maxW-1,maxH-1],[0,maxH-1]], dtype="float32")
    M    = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (maxW, maxH))


def detect_sheet(image):
    cfg   = OMRConfig
    gray  = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur  = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blur, 40, 140)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edged  = cv2.dilate(edged, kernel, iterations=1)
    cnts, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts    = sorted(cnts, key=cv2.contourArea, reverse=True)
    for cnt in cnts[:15]:
        if cv2.contourArea(cnt) < 0.1 * image.shape[0] * image.shape[1]:
            continue
        peri   = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4:
            warped = four_point_transform(image, approx.reshape(4, 2))
            return cv2.resize(warped, (cfg.CANVAS_W, cfg.CANVAS_H)), True
    return cv2.resize(image, (cfg.CANVAS_W, cfg.CANVAS_H)), False


# ─── Bubble scoring ───────────────────────────────────────────────────────────

def bubble_score(thresh, cx, cy, r):
    x1 = max(0, cx - r);  y1 = max(0, cy - r)
    x2 = min(thresh.shape[1], cx + r);  y2 = min(thresh.shape[0], cy + r)
    roi = thresh[y1:y2, x1:x2]
    if roi.size == 0:
        return 0.0
    mask = np.zeros(roi.shape, dtype=np.uint8)
    cv2.circle(mask, (roi.shape[1] // 2, roi.shape[0] // 2), r, 255, -1)
    filled = cv2.bitwise_and(roi, roi, mask=mask)
    return np.sum(filled > 0) / max(1, np.sum(mask > 0))


def pick_filled(scores):
    cfg = OMRConfig
    if not scores:
        return -1
    best   = max(scores)
    idx    = scores.index(best)
    second = sorted(scores, reverse=True)[1] if len(scores) > 1 else 0
    if best >= cfg.FILL_FRAC and (best - second) > cfg.FILL_MARGIN:
        return idx
    return -1


# ─── Read Chest No ────────────────────────────────────────────────────────────

def read_chest_no(thresh):
    cfg    = OMRConfig
    digits = []
    for d in range(cfg.CHEST_DIGITS):
        cx     = cfg.CHEST_COL_X[d]
        scores = [
            bubble_score(thresh, cx, cfg.CHEST_ROW_Y[v], cfg.CHEST_BUBBLE_R)
            for v in range(cfg.CHEST_DIGIT_VALS)
        ]
        val = pick_filled(scores)
        digits.append(str(val) if val != -1 else "?")
    return "".join(digits)


# ─── Read Company ─────────────────────────────────────────────────────────────

def read_company(thresh):
    cfg    = OMRConfig
    scores = [
        bubble_score(thresh,
                     int(cfg.COMPANY_X0 + i * cfg.COMPANY_GAP),
                     cfg.COMPANY_Y,
                     cfg.COMPANY_BUBBLE_R)
        for i in range(len(cfg.COMPANY_LABELS))
    ]
    idx = pick_filled(scores)
    return cfg.COMPANY_LABELS[idx] if idx != -1 else "?"


# ─── Read Answers ─────────────────────────────────────────────────────────────

def read_bubbles(thresh):
    cfg     = OMRConfig
    answers = []
    for q in range(cfg.NUM_QUESTIONS):
        col_idx = q // cfg.QUESTIONS_PER_COL
        row_idx = q %  cfg.QUESTIONS_PER_COL
        col     = cfg.COLS[col_idx]
        cy      = int(col["oy"] + row_idx * cfg.ROW_GAP)
        scores  = [
            bubble_score(thresh,
                         int(col["ox"] + c * cfg.CHOICE_GAP),
                         cy, cfg.BUBBLE_RADIUS)
            for c in range(cfg.NUM_CHOICES)
        ]
        answers.append(pick_filled(scores))
    return answers


# ─── Annotate ─────────────────────────────────────────────────────────────────

def annotate_sheet(sheet_img, detected, answer_key, chest_no, company):
    cfg  = OMRConfig
    out  = sheet_img.copy()
    gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    thr  = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY_INV, 21, 5)

    cv2.putText(out, f"Chest: {chest_no}  Co: {company}",
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 30, 30), 2)

    # Chest No circles
    for d in range(cfg.CHEST_DIGITS):
        cx = cfg.CHEST_COL_X[d]
        for v in range(cfg.CHEST_DIGIT_VALS):
            cy    = cfg.CHEST_ROW_Y[v]
            sc    = bubble_score(thr, cx, cy, cfg.CHEST_BUBBLE_R)
            color = (0, 160, 255) if sc >= cfg.FILL_FRAC else (180, 180, 180)
            cv2.circle(out, (cx, cy), cfg.CHEST_BUBBLE_R + 2, color, 1)

    # Company circles
    for i in range(len(cfg.COMPANY_LABELS)):
        cx    = int(cfg.COMPANY_X0 + i * cfg.COMPANY_GAP)
        cy    = cfg.COMPANY_Y
        sc    = bubble_score(thr, cx, cy, cfg.COMPANY_BUBBLE_R)
        color = (0, 220, 220) if sc >= cfg.FILL_FRAC else (180, 180, 180)
        cv2.circle(out, (cx, cy), cfg.COMPANY_BUBBLE_R + 2, color, 1)

    # Answer circles
    for q in range(cfg.NUM_QUESTIONS):
        col_idx = q // cfg.QUESTIONS_PER_COL
        row_idx = q %  cfg.QUESTIONS_PER_COL
        col     = cfg.COLS[col_idx]
        cy      = int(col["oy"] + row_idx * cfg.ROW_GAP)
        det     = detected[q]
        correct = answer_key[q] if q < len(answer_key) else -1
        for c in range(cfg.NUM_CHOICES):
            cx    = int(col["ox"] + c * cfg.CHOICE_GAP)
            r     = cfg.BUBBLE_RADIUS + 3
            color, thick = (180, 180, 180), 1
            if c == correct == det:
                color, thick = (0, 210, 80), 2
            elif c == det and det != correct:
                color, thick = (30, 30, 220), 2
            elif c == correct and det != correct:
                color, thick = (0, 140, 255), 2
            cv2.circle(out, (cx, cy), r, color, thick)

    return out


# ─── Full pipeline ────────────────────────────────────────────────────────────

def process_omr(image_path: str, answer_key: list) -> dict:
    cfg   = OMRConfig
    image = cv2.imread(image_path)
    if image is None:
        return {"error": f"Cannot read image: {image_path}"}

    sheet, sheet_detected = detect_sheet(image)
    gray   = cv2.cvtColor(sheet, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY_INV, 21, 5)

    chest_no  = read_chest_no(thresh)
    company   = read_company(thresh)
    detected  = read_bubbles(thresh)
    annotated = annotate_sheet(sheet, detected, answer_key, chest_no, company)

    correct = sum(1 for q, det in enumerate(detected)
                  if det != -1 and q < len(answer_key) and det == answer_key[q])
    blank   = detected.count(-1)
    wrong   = cfg.NUM_QUESTIONS - correct - blank
    pct     = round(correct / cfg.NUM_QUESTIONS * 100, 1)

    labels    = cfg.CHOICE_LABELS
    breakdown = [{
        "question": q + 1,
        "detected": labels[detected[q]] if detected[q] != -1 else "-",
        "correct" : labels[answer_key[q]] if q < len(answer_key) and answer_key[q] != -1 else "?",
        "status"  : ("correct" if detected[q] != -1 and detected[q] == answer_key[q]
                     else "blank" if detected[q] == -1 else "wrong"),
    } for q in range(cfg.NUM_QUESTIONS)]

    return {
        "filename"       : image_path,
        "student_id"     : chest_no,
        "company"        : company,
        "sheet_detected" : sheet_detected,
        "score"          : correct,
        "total"          : cfg.NUM_QUESTIONS,
        "score_pct"      : pct,
        "correct"        : correct,
        "wrong"          : wrong,
        "blank"          : blank,
        "breakdown"      : breakdown,
        "annotated_img"  : annotated,
    }


# ─── Sample sheet generator ───────────────────────────────────────────────────

def generate_sample_sheet(filled_answers=None, chest_digits=None, company_idx=0):
    cfg = OMRConfig
    rng = np.random.default_rng(99)
    if filled_answers is None:
        filled_answers = rng.integers(0, 4, size=cfg.NUM_QUESTIONS).tolist()
    if chest_digits is None:
        chest_digits = rng.integers(0, 10, size=cfg.CHEST_DIGITS).tolist()

    img = np.ones((cfg.CANVAS_H, cfg.CANVAS_W, 3), dtype=np.uint8) * 252
    cv2.rectangle(img, (12,12), (cfg.CANVAS_W-12, cfg.CANVAS_H-12), (30,30,30), 2)
    cv2.putText(img, "OMR ANSWER SHEET", (245, 48),
                cv2.FONT_HERSHEY_SIMPLEX, 0.85, (10,10,10), 2)
    cv2.putText(img, "Name", (25, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (60,60,60), 1)
    cv2.putText(img, "Chest No", (25, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (60,60,60), 1)

    # Chest No
    for d in range(cfg.CHEST_DIGITS):
        cx = cfg.CHEST_COL_X[d]
        for v in range(cfg.CHEST_DIGIT_VALS):
            cy    = cfg.CHEST_ROW_Y[v]
            color = (20,20,20) if v == chest_digits[d] else (200,200,200)
            thick = -1 if v == chest_digits[d] else 1
            cv2.circle(img, (cx, cy), cfg.CHEST_BUBBLE_R, color, thick)
            if d == 0:
                cv2.putText(img, str(v), (cx-18, cy+4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.28, (100,100,100), 1)

    # Company
    cv2.putText(img, "Company", (240, 268), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (60,60,60), 1)
    for i, lbl in enumerate(cfg.COMPANY_LABELS):
        cx    = int(cfg.COMPANY_X0 + i * cfg.COMPANY_GAP)
        cy    = cfg.COMPANY_Y
        color = (20,20,20) if i == company_idx else (200,200,200)
        thick = -1 if i == company_idx else 1
        cv2.circle(img, (cx, cy), cfg.COMPANY_BUBBLE_R, color, thick)
        cv2.putText(img, lbl, (cx-4, cy-13), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (80,80,80), 1)

    cv2.putText(img, "Fill circles completely using black/blue ballpen.",
                (25, 465), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (80,80,80), 1)

    # Answer grid
    for col_idx, col in enumerate(cfg.COLS):
        ox, oy = col["ox"], col["oy"]
        start  = col_idx * cfg.QUESTIONS_PER_COL
        for c, lbl in enumerate(cfg.CHOICE_LABELS):
            cv2.putText(img, lbl, (int(ox + c*cfg.CHOICE_GAP)-4, oy-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.32, (50,50,50), 1)
        for i in range(cfg.QUESTIONS_PER_COL):
            q  = start + i
            cy = int(oy + i * cfg.ROW_GAP)
            cv2.putText(img, f"{q+1:3d}", (ox-28, cy+4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.28, (70,70,70), 1)
            for c in range(cfg.NUM_CHOICES):
                cx    = int(ox + c * cfg.CHOICE_GAP)
                color = (20,20,20) if c == filled_answers[q] else (195,195,195)
                thick = -1 if c == filled_answers[q] else 1
                cv2.circle(img, (cx, cy), cfg.BUBBLE_RADIUS, color, thick)

    return img
