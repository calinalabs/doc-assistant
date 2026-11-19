"""Turn files into passages that keep their place in the source: page, section, sheet rows or email.

Each passage: {"ref": "p. 3" | "§ Exclusions" | "Sheet Rates, rows 2-14" | "email", "text": "..."}
The file name is added by the index, so every answer can cite file + ref.
"""
import email
import email.policy
import pathlib
import re

MAX_CHARS = 1800  # long pages or sections are split so each passage stays focused


def _split(ref, text):
    text = re.sub(r"[ \t]+", " ", text).strip()
    if len(text) <= MAX_CHARS:
        return [{"ref": ref, "text": text}] if text else []
    out, buf = [], ""
    for para in re.split(r"\n\s*\n", text):
        if buf and len(buf) + len(para) > MAX_CHARS:
            out.append(buf)
            buf = ""
        buf = f"{buf}\n\n{para}".strip()
    if buf:
        out.append(buf)
    if len(out) == 1:
        return [{"ref": ref, "text": out[0]}]
    return [{"ref": f"{ref} (part {i + 1})", "text": t} for i, t in enumerate(out)]


def pdf(path):
    from pypdf import PdfReader
    out = []
    for n, page in enumerate(PdfReader(str(path)).pages, 1):
        out += _split(f"p. {n}", page.extract_text() or "")
    return out


def docx(path):
    import docx as _docx
    d = _docx.Document(str(path))
    out, heading, buf = [], "Introduction", []
    for p in d.paragraphs:
        if p.style.name.lower().startswith(("heading", "title")) and p.text.strip():
            if len(buf) > 1:  # skip headings with no body text
                out += _split(f"§ {heading}", "\n".join(buf))
            heading, buf = p.text.strip(), [p.text.strip()]
        elif p.text.strip():
            buf.append(p.text.strip())
    if len(buf) > 1:
        out += _split(f"§ {heading}", "\n".join(buf))
    for t_i, table in enumerate(d.tables, 1):
        rows = [" | ".join(c.text.strip() for c in r.cells) for r in table.rows]
        out += _split(f"table {t_i}", "\n".join(rows))
    return out


def xlsx(path, rows_per_passage=12):
    from openpyxl import load_workbook
    wb = load_workbook(str(path), data_only=True, read_only=True)
    out = []
    for ws in wb.worksheets:
        rows = [r for r in ws.iter_rows(values_only=True) if any(c is not None for c in r)]
        if not rows:
            continue
        header = [str(c) if c is not None else f"col{i + 1}" for i, c in enumerate(rows[0])]
        body = rows[1:]
        for s in range(0, len(body), rows_per_passage):
            chunk = body[s:s + rows_per_passage]
            fmt = lambda v: f"{v:,}" if isinstance(v, (int, float)) and not isinstance(v, bool) else v
            lines = ["; ".join(f"{h}: {fmt(v)}" for h, v in zip(header, r) if v is not None) for r in chunk]
            first, last = s + 2, s + 1 + len(chunk)  # spreadsheet row numbers (row 1 is the header)
            out.append({"ref": f"Sheet {ws.title}, rows {first}-{last}",
                        "text": f"Sheet: {ws.title}\n" + "\n".join(lines)})
    return out


def _email_text(sender, to, date, subject, body):
    return f"From: {sender}\nTo: {to}\nDate: {date}\nSubject: {subject}\n\n{body}"


def eml(path):
    msg = email.message_from_bytes(pathlib.Path(path).read_bytes(), policy=email.policy.default)
    part = msg.get_body(preferencelist=("plain", "html"))
    body = part.get_content() if part else ""
    if part is not None and part.get_content_type() == "text/html":
        body = re.sub(r"<[^>]+>", " ", body)
    return _split("email", _email_text(msg["from"], msg["to"], msg["date"], msg["subject"], body))


def msg(path):
    import extract_msg
    m = extract_msg.Message(str(path))
    try:
        return _split("email", _email_text(m.sender, m.to, m.date, m.subject, m.body or ""))
    finally:
        m.close()


def txt(path):
    return _split("text", pathlib.Path(path).read_text(errors="replace"))


READERS = {".pdf": pdf, ".docx": docx, ".xlsx": xlsx, ".eml": eml, ".msg": msg, ".txt": txt, ".md": txt}


def supported(path):
    return pathlib.Path(path).suffix.lower() in READERS


def extract(path):
    return READERS[pathlib.Path(path).suffix.lower()](path)
