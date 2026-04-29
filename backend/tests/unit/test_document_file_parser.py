# -*- coding: utf-8 -*-
from io import BytesIO

import pytest
from docx import Document

from core.document_file_parser import extract_text_from_bytes, extract_text_from_path


def _build_docx_bytes(lines: list[str]) -> bytes:
    buffer = BytesIO()
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    document.save(buffer)
    return buffer.getvalue()


def _build_simple_pdf_bytes(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT\n/F1 18 Tf\n72 720 Td\n({escaped}) Tj\nET"
    stream_bytes = stream.encode("latin-1")
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            "3 0 obj\n"
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>\n"
            "endobj\n"
        ),
        f"4 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n{stream}\nendstream\nendobj\n",
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj.encode("latin-1")

    xref_offset = len(pdf)
    xref_lines = [f"xref\n0 {len(offsets)}\n", "0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref_lines.append(f"{offset:010d} 00000 n \n")
    trailer = (
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    )
    return pdf + "".join(xref_lines).encode("latin-1") + trailer.encode("latin-1")


def test_extract_text_from_bytes_supports_docx():
    data = _build_docx_bytes(["登录 PRD", "验证码有效期 5 分钟"])

    text = extract_text_from_bytes("login.docx", data)

    assert "登录 PRD" in text
    assert "验证码有效期 5 分钟" in text


def test_extract_text_from_path_supports_docx(tmp_path):
    docx_path = tmp_path / "requirement.docx"
    docx_path.write_bytes(_build_docx_bytes(["订单开发文档", "金额必须大于 0"]))

    text = extract_text_from_path(str(docx_path))

    assert "订单开发文档" in text
    assert "金额必须大于 0" in text


def test_extract_text_from_bytes_supports_pdf():
    text = extract_text_from_bytes("login.pdf", _build_simple_pdf_bytes("Login PRD PDF Text"))

    assert "Login PRD PDF Text" in text


def test_extract_text_from_bytes_rejects_unsupported_type():
    with pytest.raises(ValueError, match="暂不支持的文件类型"):
        extract_text_from_bytes("login.doc", b"binary")
