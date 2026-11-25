import streamlit as st
import io
import fitz
import requests
import base64
import re
import json
import hashlib
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from PIL import Image as PILImage

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None
    Credentials = None

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

WEB_APP_URL = "https://script.google.com/macros/s/AKfycbzu-1OxZDVDIt8atdm2Dmy4ujr4yrBXG92f5u8nkdzDI_86JkivJttTMKXXKtFA5SfD/exec"

LOGO_FILE = "aarons_logo.png"

# Brand colours (taken from the logo)
PURPLE = colors.HexColor("#2F1F5D")
ORANGE = colors.HexColor("#E8762C")
LILAC = colors.HexColor("#EDE7F3")
GREY_LINE = colors.HexColor("#A6A6A6")
GREY_TEXT = colors.HexColor("#595959")

st.set_page_config(
    page_title="Aaron's Demolition Quote Generator",
    layout="wide"
)

# =====================================================
# SESSION STATE
# =====================================================

defaults = {
    "show_preview": False,
    "pdf_buffer": None,
    "quote_data": {},
    "drive_saved": False,
    "drive_link": "",
    "drive_file_id": "",
    "form_id": 0,
    "editing_from": "",
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =====================================================
# HELPERS
# =====================================================

def reset_to_new_quote():
    st.session_state.form_id += 1
    st.session_state.show_preview = False
    st.session_state.pdf_buffer = None
    st.session_state.quote_data = {}
    st.session_state.drive_saved = False
    st.session_state.drive_link = ""
    st.session_state.drive_file_id = ""
    st.session_state.editing_from = ""


def clean_lines(text):
    return [line.strip() for line in str(text).split("\n") if line.strip()]


def clean_filename(text):
    text = str(text).strip()
    text = re.sub(r'[\\/*?:"<>|]', "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def esc(text):
    """Escape text for ReportLab paragraphs (&, <, >)."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        # Helvetica in ReportLab can't draw ² and ³, so use real superscripts
        .replace("²", "<super>2</super>")
        .replace("³", "<super>3</super>")
    )


def parse_amount(text):
    """'6500', '$6,500', 'AUD 6,500 + GST' -> 6500.0. Returns None if no number."""
    match = re.search(r"\d[\d,]*(?:\.\d+)?", str(text))
    if not match:
        return None
    return float(match.group(0).replace(",", ""))


def money(value):
    return f"AUD {value:,.2f}"


def validity_days(validity):
    match = re.search(r"\d+", str(validity))
    return int(match.group(0)) if match else 21


def deposit_fraction(deposit):
    match = re.search(r"(\d+)%", str(deposit))
    return int(match.group(1)) / 100 if match else 0


def payment_text(deposit, quote_validity):
    validity = f"This quotation is valid for {quote_validity} from the date issued. "

    if deposit == "100%":
        return validity + "Full payment upfront is required prior to commencement of works."

    if deposit == "Payment upon completion":
        return validity + "Payment is to be made upon completion of works unless otherwise negotiated in writing."

    if deposit == "0%":
        return validity + "No upfront deposit is required. The balance is payable upon completion of works."

    return (
        validity
        + f"A {deposit} upfront deposit is required to secure and schedule the booking. "
        "The remaining balance is payable upon completion of works unless otherwise negotiated in writing."
    )


def split_sections(text):
    """
    Turns the text box into sections.
    A line starting with '#' becomes a sub-heading (e.g. '# Shop 1').
    Numbering restarts after every sub-heading.
    """
    sections = []
    current = {"title": None, "items": []}

    for line in clean_lines(text):
        if line.startswith("#"):
            if current["title"] or current["items"]:
                sections.append(current)
            current = {"title": line.lstrip("#").strip(), "items": []}
        else:
            # Remove numbers the user may have typed ("1. ", "2) ")
            current["items"].append(re.sub(r"^\d+[.)]\s*", "", line))

    if current["title"] or current["items"]:
        sections.append(current)

    return sections


# =====================================================
# PDF GENERATOR
# =====================================================

PAGE_W, PAGE_H = A4
MARGIN_X = 50


def draw_page(canvas, doc):
    """Logo header + company footer with page number on every page."""
    canvas.saveState()

    # Header logo
    try:
        logo = ImageReader(LOGO_FILE)
        iw, ih = logo.getSize()
        w = 150
        h = w * ih / iw
        canvas.drawImage(
            logo, (PAGE_W - w) / 2, PAGE_H - 22 - h,
            width=w, height=h, mask="auto"
        )
    except Exception:
        pass

    # Footer
    canvas.setStrokeColor(GREY_LINE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_X, 58, PAGE_W - MARGIN_X, 58)

    canvas.setFillColor(GREY_TEXT)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawCentredString(PAGE_W / 2, 46, "Aaron's Demolitions – ABN 42164569733")
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(PAGE_W / 2, 35, "Unit 3, 13-17 Crawford Street Braeside VIC 3195")
    canvas.drawCentredString(
        PAGE_W / 2, 24,
        f"Phone: 0425 274 140 | Email: aaronsrr@gmail.com  |  Page {doc.page}"
    )

    canvas.restoreState()


def generate_pdf(data):
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=MARGIN_X,
        leftMargin=MARGIN_X,
        topMargin=100,
        bottomMargin=75,
        title=f"Quotation {data['quote_no']}",
        author="Aaron's Demolitions",
    )
    usable_w = PAGE_W - 2 * MARGIN_X

    styles = getSampleStyleSheet()

    normal = ParagraphStyle(
        "NormalQ", parent=styles["Normal"], fontName="Helvetica",
        fontSize=10, leading=14, alignment=TA_JUSTIFY, spaceAfter=6
    )
    normal_left = ParagraphStyle("NormalLeft", parent=normal, alignment=TA_LEFT)
    small_note = ParagraphStyle(
        "SmallNote", parent=normal_left, fontName="Helvetica-Oblique",
        fontSize=8.5, leading=11, textColor=GREY_TEXT
    )
    title_style = ParagraphStyle(
        "TitleQ", parent=normal_left, fontName="Helvetica-Bold",
        fontSize=16, leading=20, textColor=PURPLE, spaceAfter=8
    )
    heading = ParagraphStyle(
        "HeadingQ", parent=normal_left, fontName="Helvetica-Bold",
        fontSize=11.5, leading=15, textColor=PURPLE, spaceBefore=12, spaceAfter=2
    )
    sub_heading = ParagraphStyle(
        "SubHeadingQ", parent=normal_left, fontName="Helvetica-Bold",
        fontSize=10, leading=14, spaceBefore=8, spaceAfter=3
    )
    list_item = ParagraphStyle(
        "ListItem", parent=normal, leftIndent=18, bulletIndent=0,
        spaceAfter=3, leading=13.5
    )
    cell = ParagraphStyle(
        "Cell", parent=normal_left, fontSize=8.5, leading=11, spaceAfter=0
    )
    cell_bold = ParagraphStyle("CellBold", parent=cell, fontName="Helvetica-Bold")
    cell_right = ParagraphStyle("CellRight", parent=cell, alignment=TA_RIGHT)
    cell_right_bold = ParagraphStyle("CellRightBold", parent=cell_right, fontName="Helvetica-Bold")
    cell_head = ParagraphStyle("CellHead", parent=cell_bold, textColor=colors.white)
    cell_head_right = ParagraphStyle("CellHeadRight", parent=cell_head, alignment=TA_RIGHT)
    cell_center = ParagraphStyle("CellCenter", parent=cell, alignment=TA_CENTER)
    cell_head_center = ParagraphStyle("CellHeadCenter", parent=cell_head, alignment=TA_CENTER)

    def section_heading(text):
        """Purple heading with a thin purple rule underneath."""
        t = Table([[Paragraph(text, heading)]], colWidths=[usable_w])
        t.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 1, PURPLE),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return [Spacer(1, 6), t, Spacer(1, 4)]

    def numbered_sections(text):
        out = []
        for section in split_sections(text):
            if section["title"]:
                out.append(Paragraph(esc(section["title"]), sub_heading))
            for i, item in enumerate(section["items"], start=1):
                out.append(Paragraph(esc(item), list_item, bulletText=f"{i}."))
        return out

    elements = []

    # ---------- Title + details table ----------
    elements.append(Paragraph("QUOTATION", title_style))

    contact_label = "Email" if data.get("client_email") and not data.get("contact_name") else "Contact"
    contact_value = data.get("contact_name") or data.get("client_email") or ""

    second_label, second_value = ("Project", data["project"]) if data.get("project") else ("Client", data["client_name"])

    details = [
        ["Quote No.", data["quote_no"], "Date Issued", data["date_issued"]],
        [second_label, second_value, "Validity", f"{data['quote_validity']} from date issued"],
        ["Site Address", data["quote_address"], contact_label, contact_value],
    ]
    details = [
        [Paragraph(esc(r[0]), cell_bold), Paragraph(esc(r[1]), cell),
         Paragraph(esc(r[2]), cell_bold), Paragraph(esc(r[3]), cell)]
        for r in details
    ]
    dw = usable_w / 4
    details_table = Table(details, colWidths=[dw * 0.85, dw * 1.15, dw * 0.85, dw * 1.15])
    details_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, GREY_LINE),
        ("BACKGROUND", (0, 0), (0, -1), LILAC),
        ("BACKGROUND", (2, 0), (2, -1), LILAC),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 10))

    # ---------- Intro ----------
    elements.append(Paragraph(f"<b>Quotation:</b> {esc(data['job_title'])}", normal_left))

    first_name = data["client_name"].split()[0] if data["client_name"].strip() else ""
    thanks = f"Thank you, {esc(first_name)}, for" if first_name else "Thank you for"
    inspection = (
        f" carried out on {esc(data['inspection_date'])}" if data.get("inspection_date") else ""
    )
    elements.append(Paragraph(
        f"{thanks} the opportunity to quote the following works. This quotation is based on "
        f"the site inspection{inspection}, the photos taken and the information provided "
        "regarding the scope of works.", normal))

    elements.append(Paragraph(
        "Aaron's Rubbish Removal &amp; Demolition holds Public Liability Insurance of "
        "$20,000,000.00 and current WorkCover, operates under the Building and Construction "
        "General On-site Award 2020, and complies with the National Code &amp; Guidelines. "
        "All works will be carried out in accordance with OH&amp;S requirements and our "
        "Environment Health &amp; Safety Management Plan. We prioritise recycling and the "
        "minimisation of materials sent to landfill.", normal))

    if data.get("duration"):
        elements.append(Paragraph(
            f"<b>Estimated duration:</b> {esc(data['duration'])}", normal_left))

    # ---------- Inclusions ----------
    elements += section_heading("Inclusions &amp; Scope of Works")
    elements += numbered_sections(data["scope_text"])

    # Documentation (kept from the old form): added as its own block if filled in
    if data.get("documentation_text", "").strip():
        elements.append(Paragraph("Documentation", sub_heading))
        for i, item in enumerate(clean_lines(data["documentation_text"]), start=1):
            elements.append(Paragraph(esc(item), list_item, bulletText=f"{i}."))

    # Optional scope text
    if data.get("optional_text", "").strip():
        elements.append(Paragraph("Optional Scope", sub_heading))
        for i, item in enumerate(clean_lines(data["optional_text"]), start=1):
            elements.append(Paragraph(esc(item), list_item, bulletText=f"{i}."))

    # ---------- Exclusions ----------
    elements += section_heading("Exclusions &amp; Conditions")
    elements += numbered_sections(data["exclusions_text"])

    # ---------- Pricing ----------
    pricing_block = section_heading("Scope-Based Pricing")

    pw = [usable_w * 0.15, usable_w * 0.62, usable_w * 0.23]
    rows = [[
        Paragraph("Scope", cell_head_center),
        Paragraph("Description", cell_head),
        Paragraph("Price", cell_head_right),
    ]]
    shaded_rows = []
    bold_rows = []

    subtotal = 0.0
    all_numeric = True
    main_scopes = [s for s in data["scopes"] if not s["optional"]]
    optional_scopes = [s for s in data["scopes"] if s["optional"]]

    # Group the lines by scope number (Scope 1, Scope 2...)
    scope_numbers = sorted({s.get("scope_no", 1) for s in main_scopes})
    several_scopes = len(scope_numbers) > 1

    for n in scope_numbers:
        lines = [s for s in main_scopes if s.get("scope_no", 1) == n]
        scope_total = 0.0
        scope_numeric = True
        for idx, s in enumerate(lines):
            amount = parse_amount(s["price"])
            if amount is None:
                all_numeric = False
                scope_numeric = False
                price_text = s["price"]
            else:
                subtotal += amount
                scope_total += amount
                price_text = money(amount)
            rows.append([
                Paragraph(f"Scope {n}" if idx == 0 else "", cell_center),
                Paragraph(esc(s["desc"]), cell),
                Paragraph(esc(price_text), cell_right),
            ])
        # With several scopes, show each scope's own total when it has more than one line
        if several_scopes and len(lines) > 1 and scope_numeric:
            rows.append([
                "",
                Paragraph(f"Scope {n} Total", cell_bold),
                Paragraph(money(scope_total), cell_right_bold),
            ])

    if all_numeric and main_scopes:
        gst = round(subtotal * 0.10, 2)
        total = subtotal + gst
        dep = deposit_fraction(data["deposit_required"])

        totals = [("Subtotal", money(subtotal), True),
                  ("GST (10%)", money(gst), False),
                  ("Total incl. GST", money(total), True)]
        for label, value, is_bold in totals:
            r = len(rows)
            shaded_rows.append(r)
            if is_bold:
                bold_rows.append(r)
            rows.append([
                "",
                Paragraph(label, cell_bold if is_bold else cell),
                Paragraph(value, cell_right_bold if is_bold else cell_right),
            ])
        if 0 < dep < 1:
            rows.append([
                "",
                Paragraph(f"{data['deposit_required']} Deposit Required", cell_bold),
                Paragraph(money(round(total * dep, 2)), cell_right_bold),
            ])

    price_table = Table(rows, colWidths=pw, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
        ("GRID", (0, 0), (-1, -1), 0.5, GREY_LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for r in shaded_rows:
        style.append(("BACKGROUND", (0, r), (-1, r), LILAC))
    price_table.setStyle(TableStyle(style))
    pricing_block.append(price_table)

    if optional_scopes:
        orows = [[
            Paragraph("Optional", cell_head_center),
            Paragraph("Description", cell_head),
            Paragraph("Price", cell_head_right),
        ]]
        for s in optional_scopes:
            amount = parse_amount(s["price"])
            price_text = f"{money(amount)} + GST" if amount is not None else s["price"]
            orows.append([
                "",
                Paragraph(esc(s["desc"]), cell),
                Paragraph(esc(price_text), cell_right),
            ])
        opt_table = Table(orows, colWidths=pw)
        opt_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
            ("GRID", (0, 0), (-1, -1), 0.5, GREY_LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        pricing_block.append(Spacer(1, 8))
        pricing_block.append(opt_table)

    elements.append(KeepTogether(pricing_block))

    # ---------- Payment terms ----------
    payment_block = section_heading("Payment Terms")
    payment_block.append(Paragraph(
        esc(payment_text(data["deposit_required"], data["quote_validity"])), normal))
    payment_block.append(Paragraph(
        "<b>Bank Details:</b>&nbsp; Account Name: Aaron's Rubbish Removal Pty Ltd&nbsp; | &nbsp;"
        "BSB: 704191&nbsp; | &nbsp;Account Number: 246767", normal_left))
    payment_block.append(Paragraph(
        "Please confirm bank details by phone before making any payment. "
        "We will never change our bank details by email.", small_note))
    elements.append(KeepTogether(payment_block))

    doc.build(elements, onFirstPage=draw_page, onLaterPages=draw_page)

    buffer.seek(0)
    return buffer


# =====================================================
# EMAIL (HTML version with summary box)
# =====================================================

def build_email_html(quote_data, message_text):
    """
    HTML version of the email: the message, a summary box and the signature.
    Images use cid:logo and cid:banner, which the Apps Script attaches
    as inline images (see the Apps Script snippet).
    """
    paragraphs = [p.strip() for p in message_text.split("\n\n") if p.strip()]
    # Remove the plain-text sign-off; the HTML signature replaces it
    paragraphs = [p for p in paragraphs if not p.lower().startswith("kind regards")]

    def para(p):
        return f"<p>{esc(p).replace(chr(10), '<br>')}</p>"

    # Summary box goes after the "Please find attached..." paragraph
    summary = f"""
<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:16px 0;width:100%;max-width:520px;border-left:4px solid #2F1F5D;background:#F5F1F9;">
<tr><td style="padding:12px 16px;font-size:14px;line-height:1.7;color:#222222;">
<b>Quote No:</b> {esc(quote_data['quote_no'])}<br>
<b>Works:</b> {esc(quote_data['job_title'])}<br>
<b>Site:</b> {esc(quote_data['quote_address'])}
</td></tr></table>"""

    body = ""
    for i, p in enumerate(paragraphs):
        body += para(p)
        if i == 1:
            body += summary

    signature = """
<p>Kind regards,</p>
<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-top:8px;">
<tr>
<td style="padding-right:16px;vertical-align:middle;"><img src="cid:logo" alt="Aaron's Rubbish Removal &amp; Demolitions" width="180" style="display:block;width:180px;height:auto;border:0;"></td>
<td style="border-left:2px solid #E8762C;padding-left:16px;vertical-align:middle;font-size:13px;line-height:1.6;color:#333333;">
<b style="font-size:15px;color:#2F1F5D;">Lionel Castro</b><br>
Aaron's Rubbish Removal &amp; Demolitions<br>
Phone: 0425 274 140<br>
Email: <a href="mailto:aaronsrr@gmail.com" style="color:#2F1F5D;">aaronsrr@gmail.com</a><br>
<a href="https://www.aaronsrubbishremoval.com.au" style="color:#E8762C;font-weight:bold;text-decoration:none;">www.aaronsrubbishremoval.com.au</a>
</td></tr></table>
<!--BANNER--><table cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-top:14px;">
<tr><td><a href="https://www.aaronsrubbishremoval.com.au" style="text-decoration:none;border:0;"><img src="cid:banner" alt="Demolition • Strip-Out • Rubbish Removal • Site Clean-Ups" width="600" style="display:block;width:600px;max-width:100%;height:auto;border:0;"></a></td></tr>
</table><!--/BANNER-->"""

    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;'
        'line-height:1.6;color:#222222;max-width:640px;">'
        + body + signature + "</div>"
    )


# =====================================================
# SAVE TO GOOGLE SHEET + DRIVE
# =====================================================

def save_quote_to_drive_and_sheet(quote_data, pdf_buffer):
    pdf_bytes = pdf_buffer.getvalue()
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

    safe_no = clean_filename(quote_data["quote_no"])
    safe_address = clean_filename(quote_data["quote_address"])
    file_name = f"Quote {safe_no} - {safe_address}.pdf"

    # Flatten scopes so the Sheet keeps receiving scope1/price1 ... like before
    payload = {k: v for k, v in quote_data.items() if k != "scopes"}
    for i, s in enumerate(quote_data["scopes"], start=1):
        payload[f"scope{i}"] = f"[Scope {s.get('scope_no', 1)}] " + s["desc"] + (" (Optional)" if s["optional"] else "")
        payload[f"price{i}"] = s["price"]

    payload.update({
        "action": "save_quote",
        "pdf_base64": pdf_base64,
        "file_name": file_name,
    })

    return requests.post(WEB_APP_URL, json=payload, timeout=30)


def fetch_next_quote_no():
    """Asks the Apps Script for the next quote number (e.g. Q-2026-2567)."""
    try:
        response = requests.post(WEB_APP_URL, json={"action": "next_quote_no"}, timeout=15)
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "OK":
                return result.get("quote_no", "")
    except Exception:
        pass
    return ""


def load_quote_into_form(quote_no):
    """
    Asks the Apps Script for a saved quote and puts its data into a new, empty form.
    The edited quote gets the next revision number (e.g. Q-2026-2567-R1).
    Returns an error message, or "" if it worked.
    """
    try:
        response = requests.post(
            WEB_APP_URL, json={"action": "get_quote", "quote_no": quote_no}, timeout=20
        )
        result = response.json() if response.status_code == 200 else {}
    except Exception:
        return "Could not connect to Google Sheets."

    if result.get("status") != "OK":
        return result.get("message", f"Quote {quote_no} was not found.")

    q = result["quote"]

    # Start a fresh form and fill it in
    st.session_state.form_id += 1
    fid = st.session_state.form_id

    simple_fields = [
        "client_name", "project", "quote_address", "contact_name", "client_email",
        "inspection_date", "job_title", "duration", "scope_text", "optional_text",
        "exclusions_text", "documentation_text",
    ]
    for field in simple_fields:
        st.session_state[f"{field}_{fid}"] = str(q.get(field, "") or "")

    st.session_state[f"quote_no_{fid}"] = result.get("next_revision", quote_no)

    # Validity "21 days" -> 21
    days = re.search(r"\d+", str(q.get("quote_validity", "")))
    st.session_state[f"quote_validity_{fid}"] = int(days.group(0)) if days else 21

    deposit_options = ["0%", "10%", "15%", "20%", "25%", "35%", "50%", "75%", "100%", "Payment upon completion"]
    if q.get("deposit_required") in deposit_options:
        st.session_state[f"deposit_required_{fid}"] = q["deposit_required"]

    # Pricing lines were saved as "[Scope 2] Description (Optional)"
    for i in range(1, 7):
        desc = str(q.get(f"scope{i}", "") or "").strip()
        price = str(q.get(f"price{i}", "") or "").strip()
        scope_no = 1
        optional = False
        match = re.match(r"^\[Scope (\d+)\]\s*", desc)
        if match:
            scope_no = int(match.group(1))
            desc = desc[match.end():]
        if desc.endswith("(Optional)"):
            optional = True
            desc = desc[: -len("(Optional)")].strip()
        st.session_state[f"scope{i}_{fid}"] = desc
        st.session_state[f"price{i}_{fid}"] = price
        st.session_state[f"scope_no{i}_{fid}"] = scope_no if scope_no in (1, 2, 3, 4) else 1
        st.session_state[f"optional{i}_{fid}"] = optional

    st.session_state.editing_from = quote_no
    return ""


# =====================================================
# DRAFTS (saved in the "Quote Drafts" tab of the Google Sheet)
# =====================================================

DRAFTS_TAB = "Quote Drafts"
DRAFT_HEADERS = ["Draft ID", "Status", "Created", "Updated", "Client", "Site Address",
                 "Job Title", "Quote No", "Editing From", "Data"]
DRAFT_TEXT_FIELDS = [
    "client_name", "project", "quote_address", "contact_name", "client_email",
    "inspection_date", "job_title", "duration", "scope_text", "optional_text",
    "exclusions_text", "documentation_text", "deposit_required",
]
AUTOSAVE_SECONDS = 10
MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")


def melbourne_now():
    return datetime.now(MELBOURNE_TZ).replace(tzinfo=None)


def secret_value(key, default=""):
    try:
        value = st.secrets.get(key, default)
        if (value in (None, "", default)) and "gcp_service_account" in st.secrets:
            value = st.secrets["gcp_service_account"].get(key, default)
        return value
    except Exception:
        return default


def drafts_enabled():
    try:
        return gspread is not None and "gcp_service_account" in st.secrets
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def drafts_ws():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
    )
    book = gspread.authorize(creds).open(str(secret_value("DRAFTS_SPREADSHEET", "Aarons Pricing Database")))
    try:
        return book.worksheet(DRAFTS_TAB)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=DRAFTS_TAB, rows="500", cols=str(len(DRAFT_HEADERS)))
        ws.append_row(DRAFT_HEADERS, value_input_option="RAW")
        return ws


def form_snapshot(fid):
    """Everything typed in the form, as plain values (for saving a draft)."""
    data = {f: str(st.session_state.get(f"{f}_{fid}", "") or "") for f in DRAFT_TEXT_FIELDS}
    data["quote_validity"] = int(st.session_state.get(f"quote_validity_{fid}", 21) or 21)
    for i in range(1, 7):
        data[f"scope{i}"] = str(st.session_state.get(f"scope{i}_{fid}", "") or "")
        data[f"price{i}"] = str(st.session_state.get(f"price{i}_{fid}", "") or "")
        data[f"scope_no{i}"] = int(st.session_state.get(f"scope_no{i}_{fid}", 1) or 1)
        data[f"optional{i}"] = bool(st.session_state.get(f"optional{i}_{fid}", False))
    return data


def snapshot_hash(data):
    return hashlib.md5(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()


def snapshot_has_content(data):
    keys = ["client_name", "quote_address", "job_title", "scope_text", "exclusions_text", "scope1", "price1", "project"]
    return any(str(data.get(k, "")).strip() for k in keys)


def find_draft_row(ws, draft_id):
    ids = ws.col_values(1)
    for row_number, value in enumerate(ids, start=1):
        if row_number > 1 and str(value).strip() == draft_id:
            return row_number
    return None


def save_draft(fid):
    """Create or update this form's draft. Returns an error message or ''."""
    data = form_snapshot(fid)
    now = melbourne_now().strftime("%d/%m/%Y %H:%M")
    draft_id = st.session_state.get(f"draft_id_{fid}") or "D-" + melbourne_now().strftime("%Y%m%d-%H%M%S")
    created = st.session_state.get(f"draft_created_{fid}") or now
    editing_from = st.session_state.get("editing_from", "")
    row = [
        draft_id, "Draft", created, now,
        data["client_name"].strip(), data["quote_address"].strip(), data["job_title"].strip(),
        str(st.session_state.get(f"quote_no_{fid}", "")) if editing_from else "",
        editing_from, json.dumps(data),
    ]
    try:
        ws = drafts_ws()
        row_number = find_draft_row(ws, draft_id)
        if row_number:
            ws.update(f"A{row_number}:J{row_number}", [row], value_input_option="RAW")
        else:
            ws.append_row(row, value_input_option="RAW")
    except Exception as e:
        return f"The draft could not be saved ({e.__class__.__name__}). Your work is still in the form."

    st.session_state[f"draft_id_{fid}"] = draft_id
    st.session_state[f"draft_created_{fid}"] = created
    st.session_state[f"draft_hash_{fid}"] = snapshot_hash(data)
    st.session_state[f"draft_saved_at_{fid}"] = time.time()
    st.session_state[f"draft_saved_label_{fid}"] = melbourne_now().strftime("%H:%M")
    list_drafts.clear()
    return ""


def autosave_draft(fid):
    """Save the draft by itself when something changed (at most every few seconds)."""
    if not drafts_enabled() or st.session_state.get(f"finalised_{fid}"):
        return
    data = form_snapshot(fid)
    if not snapshot_has_content(data):
        return
    if snapshot_hash(data) == st.session_state.get(f"draft_hash_{fid}"):
        return
    if time.time() - st.session_state.get(f"draft_saved_at_{fid}", 0) < AUTOSAVE_SECONDS:
        return
    st.session_state[f"draft_error_{fid}"] = save_draft(fid)


def finalise_draft(fid, quote_no):
    """Mark the draft as finalised once the formal quote has been saved."""
    st.session_state[f"finalised_{fid}"] = True
    draft_id = st.session_state.get(f"draft_id_{fid}")
    if not draft_id or not drafts_enabled():
        return
    try:
        ws = drafts_ws()
        row_number = find_draft_row(ws, draft_id)
        if row_number:
            ws.update(f"B{row_number}:B{row_number}", [["Finalised"]], value_input_option="RAW")
            ws.update(f"D{row_number}:D{row_number}", [[melbourne_now().strftime("%d/%m/%Y %H:%M")]], value_input_option="RAW")
            ws.update(f"H{row_number}:H{row_number}", [[quote_no]], value_input_option="RAW")
        list_drafts.clear()
    except Exception:
        pass


@st.cache_data(ttl=60, show_spinner="Loading drafts...")
def list_drafts():
    try:
        records = drafts_ws().get_all_records(numericise_ignore=["all"])
    except TypeError:
        records = drafts_ws().get_all_records()
    except Exception:
        return [], "Could not connect to Google Sheets."
    drafts = [r for r in records if str(r.get("Status", "")).strip() == "Draft"]
    drafts.sort(key=lambda r: datetime.strptime(r["Updated"], "%d/%m/%Y %H:%M") if r.get("Updated") else datetime.min, reverse=True)
    return drafts, ""


def open_draft_callback(draft):
    """Load a draft into a fresh form."""
    try:
        data = json.loads(draft.get("Data") or "{}")
    except ValueError:
        data = {}
    st.session_state.form_id += 1
    fid = st.session_state.form_id
    for f in DRAFT_TEXT_FIELDS:
        if f == "deposit_required" and not data.get(f):
            continue
        st.session_state[f"{f}_{fid}"] = str(data.get(f, "") or "")
    st.session_state[f"quote_validity_{fid}"] = int(data.get("quote_validity", 21) or 21)
    for i in range(1, 7):
        st.session_state[f"scope{i}_{fid}"] = str(data.get(f"scope{i}", "") or "")
        st.session_state[f"price{i}_{fid}"] = str(data.get(f"price{i}", "") or "")
        scope_no = int(data.get(f"scope_no{i}", 1) or 1)
        st.session_state[f"scope_no{i}_{fid}"] = scope_no if scope_no in (1, 2, 3, 4) else 1
        st.session_state[f"optional{i}_{fid}"] = bool(data.get(f"optional{i}", False))

    st.session_state.editing_from = str(draft.get("Editing From", "") or "")
    if st.session_state.editing_from and draft.get("Quote No"):
        st.session_state[f"quote_no_{fid}"] = str(draft["Quote No"])
    st.session_state[f"draft_id_{fid}"] = str(draft.get("Draft ID", ""))
    st.session_state[f"draft_created_{fid}"] = str(draft.get("Created", ""))
    st.session_state[f"draft_hash_{fid}"] = snapshot_hash(form_snapshot(fid))
    st.session_state[f"draft_saved_at_{fid}"] = time.time()
    st.session_state[f"draft_saved_label_{fid}"] = str(draft.get("Updated", "")).split(" ")[-1]
    st.session_state.show_preview = False
    st.session_state.page = "New Quote"


def delete_draft(draft_id):
    try:
        ws = drafts_ws()
        row_number = find_draft_row(ws, draft_id)
        if row_number:
            ws.delete_rows(row_number)
        list_drafts.clear()
        return ""
    except Exception:
        return "The draft could not be deleted."


def render_drafts():
    st.title("Drafts")
    st.caption("Quotes you are still working on. They are saved automatically while you type.")

    if not drafts_enabled():
        st.warning(
            "Drafts are not set up yet. In Streamlit Cloud open this app's Settings → Secrets and paste the "
            "[gcp_service_account] block from the aarons-pricing app."
        )
        return

    top1, top2 = st.columns([4, 1])
    with top2:
        if st.button("🔄 Refresh", use_container_width=True, key="drafts_refresh"):
            list_drafts.clear()
            st.rerun()

    flash = st.session_state.pop("drafts_flash", None)
    if flash:
        st.success(flash)

    drafts, error = list_drafts()
    if error:
        st.error(error)
        return
    if not drafts:
        st.info("No drafts. Start a quote in **New Quote** and it is saved here automatically.")
        return

    rows = [{
        "Last saved": d.get("Updated", ""),
        "Client": d.get("Client", "") or "—",
        "Site Address": d.get("Site Address", "") or "—",
        "Job Title": d.get("Job Title", "") or "—",
        "Revision of": d.get("Editing From", ""),
    } for d in drafts]
    st.caption(f"{len(rows)} draft(s)")
    st.dataframe(rows, hide_index=True, use_container_width=True,
                 column_config={"Job Title": st.column_config.TextColumn(width="large")})

    labels = {
        f"{d.get('Client') or 'No client'} – {d.get('Site Address') or 'No address'} – saved {d.get('Updated', '')}": d
        for d in drafts
    }
    choice = st.selectbox("Select a draft", list(labels.keys()))
    selected = labels[choice]

    b1, b2, _ = st.columns([1, 1, 2])
    with b1:
        st.button("✏️ Open draft", on_click=open_draft_callback, args=(selected,),
                  type="primary", use_container_width=True)
    with b2:
        with st.popover("🗑️ Delete", use_container_width=True):
            st.write("Delete this draft? This can't be undone.")
            if st.button("Yes, delete", key="confirm_delete_draft"):
                error = delete_draft(str(selected.get("Draft ID", "")))
                if error:
                    st.error(error)
                else:
                    st.session_state["drafts_flash"] = "Draft deleted."
                    st.rerun()


# =====================================================
# SAVED QUOTES PAGE
# =====================================================

@st.cache_data(ttl=120, show_spinner="Loading saved quotes...")
def list_saved_quotes():
    try:
        response = requests.post(WEB_APP_URL, json={"action": "list_quotes"}, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "OK":
                return result.get("quotes", []), ""
            return [], result.get("message", "Could not load the quotes.")
    except Exception:
        pass
    return [], "Could not connect to Google Sheets."


def quote_total(q):
    """Total ex GST of the non-optional pricing lines."""
    total = 0.0
    for i in range(1, 7):
        desc = str(q.get(f"scope{i}", "") or "")
        if not desc or desc.strip().endswith("(Optional)"):
            continue
        amount = parse_amount(q.get(f"price{i}", ""))
        if amount is not None:
            total += amount
    return total


def edit_quote_callback(quote_no):
    """Runs when 'Edit as new revision' is clicked on the Saved Quotes page."""
    st.session_state.load_error = load_quote_into_form(quote_no)
    if not st.session_state.load_error:
        st.session_state.show_preview = False
        st.session_state.page = "New Quote"


def render_saved_quotes():
    st.title("Saved Quotes")

    top1, top2 = st.columns([4, 1])
    with top1:
        search = st.text_input(
            "Search", placeholder="Quote number, client, project or address",
            label_visibility="collapsed",
        )
    with top2:
        if st.button("🔄 Refresh", use_container_width=True):
            list_saved_quotes.clear()
            st.rerun()

    quotes, error = list_saved_quotes()
    if error:
        st.error(error)
        return
    if not quotes:
        st.info("No quotes saved yet.")
        return

    term = search.strip().lower()
    if term:
        fields = ["quote_no", "client_name", "project", "quote_address", "job_title"]
        quotes = [q for q in quotes if any(term in str(q.get(f, "")).lower() for f in fields)]

    rows = []
    for q in quotes:
        total = quote_total(q)
        rows.append({
            "Quote No.": q.get("quote_no") or "—",
            "Date": q.get("date_issued") or str(q.get("timestamp", "")).split(" ")[0],
            "Client": q.get("client_name", ""),
            "Project": q.get("project", ""),
            "Site Address": q.get("quote_address", ""),
            "Job Title": q.get("job_title", ""),
            "Total ex GST": f"AUD {total:,.2f}" if total else "",
            "Total incl. GST": f"AUD {total * 1.1:,.2f}" if total else "",
            "PDF": q.get("pdf_url") or None,
        })

    st.caption(f"{len(rows)} quote(s)")
    st.dataframe(
        rows,
        hide_index=True,
        use_container_width=True,
        column_config={
            "PDF": st.column_config.LinkColumn("PDF", display_text="Open PDF"),
            "Job Title": st.column_config.TextColumn(width="large"),
        },
    )

    # Open / edit one quote
    numbered = [q for q in quotes if q.get("quote_no")]
    if not numbered:
        st.caption("Quotes made before the quote number was added cannot be edited from here.")
        return

    st.subheader("Open or edit a quote")
    labels = {
        f"{q['quote_no']} – {q.get('client_name', '')} – {q.get('quote_address', '')}": q
        for q in numbered
    }
    choice = st.selectbox("Select a quote", list(labels.keys()))
    selected = labels[choice]

    b1, b2, _ = st.columns([1, 1, 2])
    with b1:
        if selected.get("pdf_url"):
            st.link_button("📄 Open PDF", selected["pdf_url"], use_container_width=True)
    with b2:
        st.button(
            "✏️ Edit as new revision",
            on_click=edit_quote_callback,
            args=(selected["quote_no"],),
            use_container_width=True,
        )

    if st.session_state.get("load_error"):
        st.error(st.session_state.load_error)


# =====================================================
# NAVIGATION (sidebar)
# =====================================================

st.session_state.setdefault("page", "New Quote")

with st.sidebar:
    st.image(LOGO_FILE, width=200)
    st.radio("Menu", ["New Quote", "Drafts", "Saved Quotes"], key="page")

if st.session_state.page == "Saved Quotes":
    render_saved_quotes()
    st.stop()

if st.session_state.page == "Drafts":
    render_drafts()
    st.stop()


# =====================================================
# FORM PAGE
# =====================================================

if not st.session_state.show_preview:

    fid = st.session_state.form_id

    # Quote number: assigned automatically by Google Sheets (not editable)
    if f"quote_no_{fid}" not in st.session_state:
        st.session_state[f"quote_no_{fid}"] = fetch_next_quote_no()

    # Default values (set here so loaded quotes can overwrite them without warnings)
    st.session_state.setdefault(f"quote_validity_{fid}", 21)
    st.session_state.setdefault(f"deposit_required_{fid}", "35%")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(LOGO_FILE, width=380)

    st.title("Aaron's Demolition Quote Generator")

    # ---------- Edit an existing quote ----------
    with st.expander("✏️ Edit an existing quote", expanded=False):
        st.caption(
            "Type the quote number and press Load. The form is filled with the saved quote, "
            "and the edited version is saved as a new revision (e.g. Q-2026-2567-R1). "
            "The original quote stays unchanged."
        )
        e1, e2 = st.columns([3, 1])
        with e1:
            load_no = st.text_input("Quote No. to edit", placeholder="Q-2026-2567", key=f"load_no_{fid}")
        with e2:
            st.write("")
            st.write("")
            load_clicked = st.button("Load quote")
        if load_clicked:
            if not load_no.strip():
                st.error("Please type a quote number.")
            else:
                error = load_quote_into_form(load_no.strip())
                if error:
                    st.error(error)
                else:
                    st.rerun()

    if st.session_state.get("editing_from"):
        st.info(
            f"Editing quote {st.session_state.editing_from}. "
            f"It will be saved as {st.session_state.get(f'quote_no_{fid}', '')}."
        )

    draft_status = st.container()

    st.subheader("Quote Details")
    c1, c2 = st.columns(2)
    with c1:
        st.text_input(
            "Quote No. (automatic)",
            value=st.session_state.get(f"quote_no_{fid}") or "Assigned when the PDF is generated",
            disabled=True,
        )
        st.text_input("Client Name *", key=f"client_name_{fid}")
        st.text_input("Project (optional – e.g. Como Centre – Daqua)", key=f"project_{fid}")
        st.text_input("Quote Address *", key=f"quote_address_{fid}")
    with c2:
        st.date_input("Date Issued", value=datetime.today(), format="DD/MM/YYYY", key=f"date_issued_{fid}")
        st.text_input("Inspection Date (optional – e.g. 11/11/2026)", key=f"inspection_date_{fid}")
        st.text_input("Contact Name (optional)", key=f"contact_name_{fid}")
        st.text_input("Client Email (optional)", key=f"client_email_{fid}")

    st.text_input("Job Title *", key=f"job_title_{fid}")
    st.text_input(
        "Estimated Duration (optional)",
        placeholder="approximately 6–7 working days. The duration may vary depending on site access and site conditions.",
        key=f"duration_{fid}",
    )

    st.caption(
        "One item per line – numbers are added automatically. "
        "Start a line with **#** to add a sub-heading (e.g. `# Shop 1`); numbering restarts under each sub-heading."
    )

    st.text_area("Inclusions & Scope of Works *", height=260, key=f"scope_text_{fid}")
    st.text_area("Optional Scope (optional)", height=80, key=f"optional_text_{fid}")
    st.text_area("Exclusions & Conditions *", height=200, key=f"exclusions_text_{fid}")
    st.text_area("Documentation (optional)", height=80, key=f"documentation_text_{fid}")

    st.subheader("Scope-Based Pricing")
    st.caption("Enter prices as numbers excluding GST (e.g. 6500). Choose the Scope number for each line: lines with the same number are grouped under that scope. Subtotal, GST, total and deposit are calculated automatically.")

    for i in range(1, 7):
        n, a, b, c = st.columns([1, 4, 1.5, 1])
        with n:
            st.selectbox(f"Line {i} Scope", [1, 2, 3, 4], key=f"scope_no{i}_{fid}")
        with a:
            st.text_input(f"Line {i} Description" + (" *" if i == 1 else ""), key=f"scope{i}_{fid}")
        with b:
            st.text_input(f"Line {i} Price (ex GST)" + (" *" if i == 1 else ""), key=f"price{i}_{fid}")
        with c:
            st.checkbox("Optional", key=f"optional{i}_{fid}")

    c1, c2 = st.columns(2)
    with c1:
        st.number_input(
            "Quote Validity (days)",
            min_value=1, max_value=365, step=1,
            key=f"quote_validity_{fid}",
        )
    with c2:
        st.selectbox(
            "Deposit Required",
            ["0%", "10%", "15%", "20%", "25%", "35%", "50%", "75%", "100%", "Payment upon completion"],
            key=f"deposit_required_{fid}",
        )

    col_a, col_d, col_b = st.columns([1, 1, 1])
    with col_a:
        generate_button = st.button("Generate Formal PDF Preview")
    with col_d:
        save_draft_button = st.button("💾 Save draft", disabled=not drafts_enabled())
    with col_b:
        if st.button("New Quote / Clear Form"):
            reset_to_new_quote()
            st.rerun()

    if save_draft_button:
        if not snapshot_has_content(form_snapshot(fid)):
            st.warning("Type at least the client, address or job title before saving a draft.")
        else:
            st.session_state[f"draft_error_{fid}"] = save_draft(fid)
            if not st.session_state[f"draft_error_{fid}"]:
                st.success("Draft saved. You can find it in **Drafts**.")
    elif not generate_button:
        autosave_draft(fid)

    with draft_status:
        if st.session_state.get(f"draft_error_{fid}"):
            st.warning(st.session_state[f"draft_error_{fid}"])
        elif st.session_state.get(f"draft_id_{fid}") and not st.session_state.get(f"finalised_{fid}"):
            unsaved = snapshot_hash(form_snapshot(fid)) != st.session_state.get(f"draft_hash_{fid}")
            label = st.session_state.get(f"draft_saved_label_{fid}", "")
            st.caption(
                "📝 Draft · unsaved changes – they save by themselves when you keep working, or tap 💾 Save draft"
                if unsaved else f"📝 Draft saved {label}"
            )
        elif not drafts_enabled():
            st.caption("Drafts are not set up yet (see the Drafts page).")

    if generate_button:
        g = lambda name: st.session_state.get(f"{name}_{fid}", "")

        # Confirm the quote number with Google Sheets just before saving, so two quotes
        # never get the same number. Once generated, the number stays fixed for this quote
        # (going back to edit and generating again updates the same quote).
        # Revisions (loaded quotes) keep their -R number.
        if not st.session_state.get(f"no_locked_{fid}") and not st.session_state.get("editing_from"):
            st.session_state[f"quote_no_{fid}"] = fetch_next_quote_no()
        if not str(st.session_state.get(f"quote_no_{fid}", "")).strip():
            st.session_state[f"quote_no_{fid}"] = fetch_next_quote_no()
        if not str(st.session_state.get(f"quote_no_{fid}", "")).strip():
            st.error("Could not get the next quote number from Google Sheets. Please try again.")
            st.stop()
        st.session_state[f"no_locked_{fid}"] = True

        required = [g("client_name"), g("quote_address"), g("job_title"),
                    g("scope_text"), g("exclusions_text"), g("scope1"), g("price1")]
        if any(not str(f).strip() for f in required):
            st.error("Please complete all required fields marked with *")
            st.stop()

        issued = st.session_state.get(f"date_issued_{fid}") or datetime.today()
        valid_until = issued + timedelta(days=int(g("quote_validity") or 21))

        scopes = []
        for i in range(1, 7):
            desc = str(g(f"scope{i}")).strip()
            price = str(g(f"price{i}")).strip()
            if desc:
                scopes.append({
                    "desc": desc,
                    "price": price,
                    "optional": bool(st.session_state.get(f"optional{i}_{fid}", False)),
                    "scope_no": int(st.session_state.get(f"scope_no{i}_{fid}", 1) or 1),
                })

        quote_data = {
            "quote_no": g("quote_no").strip(),
            "client_name": g("client_name").strip(),
            "project": g("project").strip(),
            "quote_address": g("quote_address").strip(),
            "contact_name": g("contact_name").strip(),
            "client_email": g("client_email").strip(),
            "inspection_date": g("inspection_date").strip(),
            "date_issued": issued.strftime("%d/%m/%Y"),
            "valid_until": valid_until.strftime("%d/%m/%Y"),
            "job_title": g("job_title").strip(),
            "duration": g("duration").strip(),
            "scope_text": g("scope_text"),
            "optional_text": g("optional_text"),
            "exclusions_text": g("exclusions_text"),
            "documentation_text": g("documentation_text"),
            "scopes": scopes,
            "quote_validity": f"{int(g('quote_validity') or 21)} days",
            "deposit_required": g("deposit_required"),
        }

        pdf_buffer = generate_pdf(quote_data)

        try:
            response = save_quote_to_drive_and_sheet(quote_data, pdf_buffer)
            list_saved_quotes.clear()
            if response.status_code == 200:
                result = response.json()
                st.session_state.drive_saved = True
                st.session_state.drive_link = result.get("file_url", "")
                st.session_state.drive_file_id = result.get("file_id", "")
            else:
                st.session_state.drive_saved = False
        except Exception:
            st.session_state.drive_saved = False

        if st.session_state.drive_saved:
            finalise_draft(fid, quote_data["quote_no"])

        st.session_state.quote_data = quote_data
        st.session_state.pdf_buffer = pdf_buffer
        st.session_state.show_preview = True
        st.rerun()


# =====================================================
# PREVIEW PAGE
# =====================================================

else:

    st.title("PDF Preview")

    if st.session_state.drive_saved:
        st.success("PDF saved to Google Drive and quote registered in Google Sheet.")
        if st.session_state.drive_link:
            st.markdown(f"[Open PDF in Google Drive]({st.session_state.drive_link})")
    else:
        st.warning("PDF was generated, but it may not have been saved to Google Drive.")

    pdf_buffer = st.session_state.pdf_buffer
    quote_data = st.session_state.quote_data
    pdf_bytes = pdf_buffer.getvalue()

    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_number in range(len(pdf_doc)):
        page = pdf_doc.load_page(page_number)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
        st.image(img, caption=f"Page {page_number + 1}", width="stretch")

    file_name = clean_filename(f"Quote {quote_data['quote_no']} - {quote_data['quote_address']}") + ".pdf"

    st.download_button(label="Download PDF", data=pdf_bytes, file_name=file_name, mime="application/pdf")

    st.divider()
    st.subheader("Email Quote")

    first_name = quote_data["client_name"].split()[0] if quote_data["client_name"] else ""
    default_subject = f"Quotation {quote_data['quote_no']} – {quote_data['job_title']}"

    default_message = f"""Dear {first_name},

Please find attached our quotation for the requested works at {quote_data['quote_address']}.

We kindly ask you to review the attached quotation at your convenience. Should you require any further information, clarification, amendments, or wish to proceed with the works, please do not hesitate to contact our team.

Thank you for considering Aaron's Rubbish Removal & Demolitions. We appreciate the opportunity to provide our services and look forward to assisting you.

Kind regards,
Lionel Castro
Aaron's Rubbish Removal & Demolitions
Phone: 0425 274 140
www.aaronsrubbishremoval.com.au
"""

    to_email = st.text_input("To", value=quote_data.get("client_email", ""))
    cc_email = st.text_input("CC", value="lionelcastropalomino@gmail.com")
    email_subject = st.text_input("Subject", value=default_subject)
    email_message = st.text_area("Message", value=default_message, height=300)

    with st.expander("Preview email design"):
        st.html(build_email_html(quote_data, email_message)
                .replace('src="cid:logo"', 'src="" style="display:none"')
                .replace('src="cid:banner"', 'src="" style="display:none"'))
        st.caption("Logo and banner are added by the Apps Script when the email is sent.")

    if st.button("Send Email with PDF"):

        if not to_email.strip():
            st.error("Please enter the recipient email.")
            st.stop()

        if not st.session_state.drive_file_id:
            st.error("PDF file was not saved to Drive.")
            st.stop()

        email_payload = {
            "action": "send_email",
            "file_id": st.session_state.drive_file_id,
            "to_email": to_email,
            "cc_email": cc_email,
            "client_name": quote_data["client_name"],
            "quote_address": quote_data["quote_address"],
            "subject": email_subject,
            "message": email_message,                                  # plain text (fallback)
            "html_message": build_email_html(quote_data, email_message),  # new HTML version
        }

        try:
            response = requests.post(WEB_APP_URL, json=email_payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "OK":
                    st.success("Email sent successfully.")
                    reset_to_new_quote()
                    st.rerun()
                else:
                    st.error(result.get("message", "Email could not be sent."))
            else:
                st.error("Email could not be sent.")
        except Exception:
            st.error("Email sending failed.")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Back to Edit Form"):
            st.session_state.show_preview = False
            st.rerun()
    with col2:
        if st.button("New Quote / Clear Everything"):
            reset_to_new_quote()
            st.rerun()
