import io
import json
import os
import time
import zipfile
from pathlib import Path

import numpy as np
import pikepdf
import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

from app.main import app

client = TestClient(app)


def _make_photo_bytes(w: int = 1200, h: int = 900, fmt: str = "PNG", seed: int = 7) -> bytes:
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w]
    img = np.zeros((h, w, 3), dtype=np.float32)
    img[:, :, 0] = (x / float(w)) * 200 + 25
    img[:, :, 1] = (y / float(h)) * 185 + 35
    img[:, :, 2] = ((x + y) / float(w + h)) * 215 + 15
    noise = rng.normal(0, 18, (h, w, 3))
    arr = np.clip(img + noise, 0, 255).astype(np.uint8)
    pil = Image.fromarray(arr)
    draw = ImageDraw.Draw(pil)
    draw.rectangle([40, 40, w - 40, h - 40], outline=(255, 255, 255), width=6)
    buf = io.BytesIO()
    pil.save(buf, format=fmt)
    return buf.getvalue()


def _wait_for_job(job_id: str, timeout_s: float = 45.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = client.get(f"/api/v1/pdf/status/{job_id}")
        assert r.status_code == 200
        data = r.json()
        if data["state"] in ("completed", "failed", "cancelled"):
            return data
        time.sleep(0.15)
    raise TimeoutError(f"Job {job_id} did not finish within {timeout_s}s")


def test_health_endpoint():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["engines"]["ghostscript"] != "unavailable"
    assert body["engines"]["qpdf"] != "unavailable"


def test_security_rejects_non_pdf_and_corrupted():
    # Disguised non-PDF file
    r1 = client.post(
        "/api/v1/pdf/upload",
        files={"file": ("evil.pdf", b"<html>not a pdf</html>", "application/pdf")},
    )
    assert r1.status_code == 400
    assert r1.json()["error"]["code"] == "INVALID_PDF"

    # Empty file
    r2 = client.post(
        "/api/v1/pdf/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert r2.status_code == 400
    assert r2.json()["error"]["code"] == "EMPTY_PDF"

    # Corrupted PDF with valid magic header
    r3 = client.post(
        "/api/v1/pdf/upload",
        files={"file": ("broken.pdf", b"%PDF-1.7\n1 0 obj\n<<GARBAGE_STREAM_CORRUPT", "application/pdf")},
    )
    assert r3.status_code == 422
    assert r3.json()["error"]["code"] == "CORRUPTED_PDF"


def test_01_text_based_pdf_preserves_searchability_and_links():
    doc = fitz.open()
    for i in range(4):
        p = doc.new_page(width=595, height=842)
        p.insert_text((72, 80), f"Chapter {i + 1}: Searchable Text Verification", fontsize=16)
        p.insert_textbox(
            fitz.Rect(72, 120, 523, 760),
            ("Precision PDF compression preserves vector glyphs and searchable text streams. " * 25),
            fontsize=11,
        )
        p.insert_link(
            {"kind": fitz.LINK_URI, "from": fitz.Rect(72, 770, 250, 795), "uri": "https://example.org"}
        )
    doc.set_toc([[1, "Chapter 1", 1], [1, "Chapter 2", 2]])
    # Pad metadata bloat to ensure structural compression reduces size
    doc.set_xml_metadata("<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>" + (" " * 18000) + "<?xpacket end='w'?>")
    pdf_bytes = doc.tobytes()
    doc.close()

    up = client.post("/api/v1/pdf/upload", files={"file": ("text_doc.pdf", pdf_bytes, "application/pdf")})
    assert up.status_code == 201
    analysis = up.json()
    assert analysis["has_searchable_text"] is True
    assert analysis["page_count"] == 4

    comp = client.post("/api/v1/pdf/compress", json={"file_id": analysis["file_id"], "preset": "recommended"})
    assert comp.status_code == 202
    status = _wait_for_job(comp.json()["job_id"])
    assert status["state"] == "completed"
    assert status["result"]["compressed_size_bytes"] < len(pdf_bytes)
    assert status["result"]["searchable_text_preserved"] is True

    dl = client.get(f"/api/v1/pdf/download/{status['job_id']}")
    assert dl.status_code == 200
    out_doc = fitz.open(stream=dl.content, filetype="pdf")
    assert out_doc.page_count == 4
    assert "Searchable Text Verification" in out_doc[0].get_text("text")
    assert len(out_doc[0].get_links()) >= 1
    assert len(out_doc.get_toc()) == 2
    out_doc.close()


def test_02_and_10_multi_page_scanned_pdf_and_custom_target():
    doc = fitz.open()
    for pno in range(3):
        p = doc.new_page(width=595, height=842)
        scan_bytes = _make_photo_bytes(1100, 1500, fmt="PNG", seed=100 + pno)
        p.insert_image(fitz.Rect(18, 18, 577, 824), stream=scan_bytes)
    raw = doc.tobytes()
    doc.close()

    up = client.post("/api/v1/pdf/upload", files={"file": ("scanned_3p.pdf", raw, "application/pdf")})
    assert up.status_code == 201
    info = up.json()
    assert info["content_profile"] in ("scanned", "image_heavy")

    # Compress to custom target 450 KB
    c_req = client.post(
        "/api/v1/pdf/compress/custom",
        json={
            "file_id": info["file_id"],
            "target_value": 450,
            "target_unit": "KB",
            "intensity": 65,
        },
    )
    assert c_req.status_code == 202
    done = _wait_for_job(c_req.json()["job_id"])
    assert done["state"] == "completed"
    res = done["result"]
    assert res["target_status"] == "met_target"
    assert res["compressed_size_bytes"] <= 450 * 1024
    assert res["page_count"] == 3


def test_03_and_04_image_heavy_and_mixed_pdf_custom_target_and_impossible_floor():
    doc = fitz.open()
    for i in range(4):
        p = doc.new_page(width=612, height=792)
        p.insert_text((50, 55), f"Mixed Report Page {i + 1}", fontsize=15)
        p.insert_textbox(fitz.Rect(50, 80, 560, 200), "Analytical commentary with embedded photography. " * 12)
        p.insert_image(fitz.Rect(50, 220, 560, 720), stream=_make_photo_bytes(1400, 1000, seed=50 + i))
    raw = doc.tobytes()
    doc.close()

    up = client.post("/api/v1/pdf/upload", files={"file": ("mixed_report.pdf", raw, "application/pdf")})
    assert up.status_code == 201
    fid = up.json()["file_id"]

    # Impossible tiny target (e.g., 2 KB for a 4-page photo+text PDF) -> must return floor_reached with required message!
    imp = client.post(
        "/api/v1/pdf/compress/custom",
        json={"file_id": fid, "target_value": 2, "target_unit": "KB", "intensity": 80},
    )
    done_imp = _wait_for_job(imp.json()["job_id"])
    assert done_imp["state"] == "completed"
    assert done_imp["result"]["target_status"] == "floor_reached"
    assert "Unable to reach your requested target size without significantly affecting document quality" in done_imp["result"]["status_message"]
    assert done_imp["result"]["validation_passed"] is True

    # Target larger than original -> already_below_target
    big = client.post(
        "/api/v1/pdf/compress/custom",
        json={"file_id": fid, "target_value": 95, "target_unit": "MB"},
    )
    done_big = _wait_for_job(big.json()["job_id"])
    assert done_big["state"] == "completed"
    assert done_big["result"]["target_status"] == "already_below_target"


def test_05_large_105_page_pdf():
    doc = fitz.open()
    shared_img = _make_photo_bytes(600, 400, seed=9)
    # Insert image on page 0 and reference text + vectors across 105 pages
    for idx in range(105):
        p = doc.new_page(width=595, height=842)
        p.insert_text((60, 70), f"Large Specification Document — Page {idx + 1} of 105", fontsize=13)
        p.insert_textbox(fitz.Rect(60, 100, 535, 420), ("Enterprise compliance paragraph content. " * 18))
        if idx % 25 == 0:
            p.insert_image(fitz.Rect(60, 440, 460, 720), stream=shared_img)
    raw = doc.tobytes()
    doc.close()

    up = client.post("/api/v1/pdf/upload", files={"file": ("large_105p.pdf", raw, "application/pdf")})
    assert up.status_code == 201
    assert up.json()["page_count"] == 105

    job = client.post("/api/v1/pdf/compress", json={"file_id": up.json()["file_id"], "preset": "high"})
    done = _wait_for_job(job.json()["job_id"])
    assert done["state"] == "completed"
    assert done["result"]["page_count"] == 105
    assert done["result"]["compressed_size_bytes"] < len(raw)


def test_06_password_protected_pdf_rejected_gracefully():
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((72, 72), "Top Secret Encrypted Document")
    enc_bytes = doc.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner123",
        user_pw="secret123",
    )
    doc.close()

    r = client.post("/api/v1/pdf/upload", files={"file": ("locked.pdf", enc_bytes, "application/pdf")})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "PASSWORD_PROTECTED_PDF"


def test_07_already_optimized_pdf_never_inflates():
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((72, 72), "Minimal Tight PDF")
    minimal_bytes = doc.tobytes(garbage=4, deflate=True, clean=True, use_objstms=1)
    doc.close()

    up = client.post("/api/v1/pdf/upload", files={"file": ("tight.pdf", minimal_bytes, "application/pdf")})
    assert up.status_code == 201
    job = client.post("/api/v1/pdf/compress", json={"file_id": up.json()["file_id"], "preset": "low"})
    done = _wait_for_job(job.json()["job_id"])
    assert done["state"] == "completed"
    assert done["result"]["compressed_size_bytes"] <= len(minimal_bytes)


def test_08_and_09_vector_graphics_and_embedded_fonts_pdf():
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(595, 842))
    # Embed a real TrueType system font if available so font subsetting exercises real TTF streams
    ttf_candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    ]
    used_font = "Helvetica"
    for cand in ttf_candidates:
        if os.path.exists(cand):
            pdfmetrics.registerFont(TTFont("EmbeddedTestFont", cand))
            used_font = "EmbeddedTestFont"
            break

    c.setFont(used_font, 14)
    c.drawString(60, 780, "Vector Engineering Diagram & Embedded Font Test")
    for k in range(60):
        c.setStrokeColorRGB((k % 5) * 0.2, 0.3, 0.7)
        c.circle(297, 420, 20 + k * 3.5, stroke=1, fill=0)
        c.line(60, 120 + k * 8, 535, 700 - k * 8)
    c.showPage()
    c.save()
    raw = buf.getvalue()

    up = client.post("/api/v1/pdf/upload", files={"file": ("vectors_fonts.pdf", raw, "application/pdf")})
    assert up.status_code == 201
    assert up.json()["has_vector_graphics"] is True

    job = client.post("/api/v1/pdf/compress", json={"file_id": up.json()["file_id"], "preset": "recommended"})
    done = _wait_for_job(job.json()["job_id"])
    assert done["state"] == "completed"
    assert done["result"]["compressed_size_bytes"] <= len(raw)


def test_batch_compression_partial_failure_and_zip_download_and_delete():
    # Valid PDF 1
    d1 = fitz.open()
    p1 = d1.new_page()
    p1.insert_image(fitz.Rect(40, 40, 500, 500), stream=_make_photo_bytes(800, 800, seed=1))
    b1 = d1.tobytes()
    d1.close()

    # Valid PDF 2
    d2 = fitz.open()
    p2 = d2.new_page()
    p2.insert_image(fitz.Rect(40, 40, 500, 500), stream=_make_photo_bytes(900, 700, seed=2))
    b2 = d2.tobytes()
    d2.close()

    settings_payload = json.dumps([
        {"index": 0, "mode": "preset", "preset": "high"},
        {"index": 1, "mode": "preset", "preset": "recommended"},
        {"index": 2, "mode": "custom", "target_value": 200, "target_unit": "KB"},
    ])

    resp = client.post(
        "/api/v1/pdf/compress/batch",
        files=[
            ("files", ("batch_one.pdf", b1, "application/pdf")),
            ("files", ("bad_middle.pdf", b"NOT_A_PDF", "application/pdf")),
            ("files", ("batch_three.pdf", b2, "application/pdf")),
        ],
        data={"settings_json": settings_payload},
    )
    assert resp.status_code == 202
    batch = resp.json()
    assert batch["total_files"] == 3
    assert batch["queued_count"] == 2
    assert batch["failed_count"] == 1
    assert batch["items"][1]["status"] == "failed"

    good_job_ids = [item["job_id"] for item in batch["items"] if item["status"] == "queued"]
    for jid in good_job_ids:
        st = _wait_for_job(jid)
        assert st["state"] == "completed"

    zip_resp = client.post("/api/v1/pdf/download/zip", json={"job_ids": good_job_ids})
    assert zip_resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(zip_resp.content))
    assert len(zf.namelist()) == 2

    # Privacy delete check
    for jid in good_job_ids:
        del_r = client.delete(f"/api/v1/pdf/{jid}")
        assert del_r.status_code == 200
        assert del_r.json()["deleted"] is True
        after = client.get(f"/api/v1/pdf/status/{jid}")
        assert after.status_code == 404
