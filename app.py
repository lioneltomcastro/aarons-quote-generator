import streamlit as st
import io
import fitz
import requests
import base64
import re
from datetime import datetime
from PIL import Image as PILImage

from reportlab.platypus import *
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib import colors

WEB_APP_URL = "https://script.google.com/macros/s/AKfycbzu-1OxZDVDIt8atdm2Dmy4ujr4yrBXG92f5u8nkdzDI_86JkivJttTMKXXKtFA5SfD/exec"

st.set_page_config(
    page_title="Aaron's Demolition Quote Generator",
    layout="wide"
)

if "show_preview" not in st.session_state:
    st.session_state.show_preview = False

if "pdf_buffer" not in st.session_state:
    st.session_state.pdf_buffer = None

if "quote_data" not in st.session_state:
    st.session_state.quote_data = {}

if "drive_saved" not in st.session_state:
    st.session_state.drive_saved = False

if "drive_link" not in st.session_state:
    st.session_state.drive_link = ""

if "drive_file_id" not in st.session_state:
    st.session_state.drive_file_id = ""


def clean_lines(text):
    return [line.strip() for line in str(text).split("\n") if line.strip()]


def clean_filename(text):
    text = str(text).strip()
    text = re.sub(r'[\\/*?:"<>|]', "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def payment_text(deposit):
    if deposit == "100%":
        return "Full payment upfront is required prior to commencement of works."

    if deposit == "Payment upon completion":
        return "Payment is to be made upon completion of works unless negotiated otherwise at the time of contract."

    if deposit == "0%":
        return "No upfront deposit is required. The balance is to be paid upon completion of works."

    return (
        f"Strictly {deposit} upfront deposit is required to secure and schedule the booking. "
        f"The remaining balance is to be paid upon completion of works unless negotiated otherwise."
    )


def clear_form():
    keys = [
        "client_name",
        "client_email",
        "quote_address",
        "job_title",
        "scope_text",
        "exclusions_text",
        "documentation_text",
        "scope1",
        "price1",
        "scope2",
        "price2",
        "scope3",
        "price3",
        "scope4",
        "price4",
        "pdf_buffer",
        "quote_data",
        "drive_saved",
        "drive_link",
        "drive_file_id"
    ]

    for key in keys:
        if key in st.session_state:
            del st.session_state[key]

    st.session_state.show_preview = False


def add_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)

    canvas.drawCentredString(
        300,
        38,
        "Aaron's Demolitions – ABN 42164569733"
    )

    canvas.drawCentredString(
        300,
        26,
        "Unit 3, 13-17 Crawford Street Braeside VIC 3195"
    )

    canvas.drawCentredString(
        300,
        14,
        "Phone: 0425 274 140 | Email: aaronsrr@gmail.com"
    )

    canvas.restoreState()


def generate_pdf(data):
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=45,
        leftMargin=45,
        topMargin=45,
        bottomMargin=70
    )

    styles = getSampleStyleSheet()

    normal = ParagraphStyle(
        "Normal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=18,
        alignment=TA_JUSTIFY,
        spaceAfter=8
    )

    heading = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=18,
        alignment=TA_LEFT,
        spaceBefore=14,
        spaceAfter=12
    )

    table_text = ParagraphStyle(
        "TableText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        alignment=TA_JUSTIFY
    )

    elements = []

    logo = Image("aarons_logo.png", width=300, height=120)
    logo.hAlign = "CENTER"

    elements.append(logo)
    elements.append(Spacer(1, 45))

    elements.append(
        Paragraph(
            f"<b>Quote:</b> {data['quote_address']}",
            normal
        )
    )

    elements.append(Spacer(1, 10))

    intro = f"""
    Thank you, {data['client_name']}, for the opportunity to quote the following work. I have relied upon discussions and the information provided regarding the scope of works.
    <br/><br/>
    Aaron's Demolitions ensures all work will be performed within OH&S requirements and compliant with our Environment Health & Safety Management Plan. Safe Work Method Statements will be supplied upon commencement of work if required.
    <br/><br/>
    Aaron's Demolitions has Public Liability Insurance at $20,000,000.00, current Work Cover, operating within the Building & Construction General On-Site Award 2010, and is compliant with the National Code & Guidelines.
    <br/><br/>
    Please note that the term “Dismantling” is used instead of “Demolition” in order to emphasize our principles of recycling and the minimization of materials to landfills. In order to achieve this, all salvage becomes the property of Aaron's Demolitions.
    <br/><br/>
    Attention
    """

    elements.append(Paragraph(intro, normal))
    elements.append(PageBreak())

    elements.append(
        Paragraph(
            f"<b>Quotation:</b> {data['job_title']}",
            normal
        )
    )

    elements.append(
        Paragraph(
            f"<b>Location:</b> {data['quote_address']}",
            normal
        )
    )

    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Inclusions & Scope of Works", heading))

    for i, item in enumerate(clean_lines(data["scope_text"]), start=1):
        elements.append(Paragraph(f"{i}. {item}", normal))

    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Exclusions", heading))

    for i, item in enumerate(clean_lines(data["exclusions_text"]), start=1):
        elements.append(Paragraph(f"{i}. {item}", normal))

    elements.append(Spacer(1, 12))

    if data["documentation_text"].strip():
        elements.append(Paragraph("Documentation", heading))

        for i, item in enumerate(clean_lines(data["documentation_text"]), start=1):
            elements.append(Paragraph(f"{i}. {item}", normal))

    elements.append(Spacer(1, 18))

    pricing_rows = []

    for i in range(1, 5):
        desc = data.get(f"scope{i}", "").strip()
        price = data.get(f"price{i}", "").strip()

        if desc:
            pricing_rows.append([
                f"Scope {i}",
                Paragraph(desc, table_text),
                Paragraph(price, table_text)
            ])

    pricing_block = []

    pricing_block.append(Paragraph("Scope-Based Pricing", heading))

    table_data = [["Scope", "Description", "Price"]] + pricing_rows

    pricing_table = Table(
        table_data,
        colWidths=[70, 320, 110],
        repeatRows=1
    )

    pricing_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (2, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    pricing_block.append(pricing_table)
    pricing_block.append(Spacer(1, 14))

    validity_text = (
        f"This quotation is valid for {data['quote_validity']} from the date issued."
    )

    pricing_block.append(Paragraph(validity_text, normal))
    pricing_block.append(Paragraph(payment_text(data["deposit_required"]), normal))
    pricing_block.append(Spacer(1, 10))

    bank_details = """
    <b>Bank Details</b><br/>
    Account Name: Aaron's Rubbish Removal Pty Ltd<br/>
    BSB: 704191<br/>
    Account Number: 246767
    """

    pricing_block.append(Paragraph(bank_details, normal))

    elements.append(KeepTogether(pricing_block))

    doc.build(
        elements,
        onFirstPage=add_footer,
        onLaterPages=add_footer
    )

    buffer.seek(0)
    return buffer


def save_quote_to_drive_and_sheet(quote_data, pdf_buffer):
    pdf_bytes = pdf_buffer.getvalue()

    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    safe_address = clean_filename(quote_data["quote_address"])

    file_name = f"Quote - {safe_address} - {timestamp}.pdf"

    payload = {
        **quote_data,
        "action": "save_quote",
        "pdf_base64": pdf_base64,
        "file_name": file_name
    }

    response = requests.post(
        WEB_APP_URL,
        json=payload,
        timeout=30
    )

    return response


if not st.session_state.show_preview:

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.image("aarons_logo.png", width=380)

    st.title("Aaron's Demolition Quote Generator")

    st.subheader("Quote Form")

    st.text_input("Client Name *", key="client_name")
    st.text_input("Client Email", key="client_email")
    st.text_input("Quote Address *", key="quote_address")
    st.text_input("Job Title *", key="job_title")

    st.text_area(
        "Inclusions & Scope of Works *",
        height=220,
        key="scope_text"
    )

    st.text_area(
        "Exclusions *",
        height=180,
        key="exclusions_text"
    )

    st.text_area(
        "Documentation",
        height=120,
        key="documentation_text"
    )

    st.subheader("Scope-Based Pricing")

    st.text_input("Scope 1 Description *", key="scope1")
    st.text_input("Scope 1 Price *", key="price1")

    st.text_input("Scope 2 Description", key="scope2")
    st.text_input("Scope 2 Price", key="price2")

    st.text_input("Scope 3 Description", key="scope3")
    st.text_input("Scope 3 Price", key="price3")

    st.text_input("Scope 4 Description", key="scope4")
    st.text_input("Scope 4 Price", key="price4")

    st.selectbox(
        "Quote Validity",
        [
            "7 days",
            "14 days",
            "21 days",
            "28 days",
            "30 days",
            "60 days",
            "90 days"
        ],
        key="quote_validity"
    )

    st.selectbox(
        "Deposit Required",
        [
            "0%",
            "10%",
            "15%",
            "20%",
            "25%",
            "35%",
            "50%",
            "75%",
            "100%",
            "Payment upon completion"
        ],
        key="deposit_required"
    )

    col_a, col_b = st.columns([1, 1])

    with col_a:
        generate_button = st.button("Generate Formal PDF Preview")

    with col_b:
        st.button(
            "New Quote / Clear Form",
            on_click=clear_form
        )

    if generate_button:

        required_fields = [
            st.session_state.client_name,
            st.session_state.quote_address,
            st.session_state.job_title,
            st.session_state.scope_text,
            st.session_state.exclusions_text,
            st.session_state.scope1,
            st.session_state.price1
        ]

        if any(not field for field in required_fields):
            st.error("Please complete all required fields marked with *")
            st.stop()

        quote_data = {
            "client_name": st.session_state.client_name,
            "client_email": st.session_state.client_email,
            "quote_address": st.session_state.quote_address,
            "job_title": st.session_state.job_title,
            "scope_text": st.session_state.scope_text,
            "exclusions_text": st.session_state.exclusions_text,
            "documentation_text": st.session_state.documentation_text,
            "scope1": st.session_state.scope1,
            "price1": st.session_state.price1,
            "scope2": st.session_state.scope2,
            "price2": st.session_state.price2,
            "scope3": st.session_state.scope3,
            "price3": st.session_state.price3,
            "scope4": st.session_state.scope4,
            "price4": st.session_state.price4,
            "quote_validity": st.session_state.quote_validity,
            "deposit_required": st.session_state.deposit_required,
        }

        pdf_buffer = generate_pdf(quote_data)

        try:
            response = save_quote_to_drive_and_sheet(
                quote_data,
                pdf_buffer
            )

            if response.status_code == 200:
                result = response.json()

                st.session_state.drive_saved = True
                st.session_state.drive_link = result.get("file_url", "")
                st.session_state.drive_file_id = result.get("file_id", "")

            else:
                st.session_state.drive_saved = False
                st.session_state.drive_link = ""
                st.session_state.drive_file_id = ""

        except Exception:
            st.session_state.drive_saved = False
            st.session_state.drive_link = ""
            st.session_state.drive_file_id = ""

        st.session_state.quote_data = quote_data
        st.session_state.pdf_buffer = pdf_buffer
        st.session_state.show_preview = True

        st.rerun()

else:

    st.title("PDF Preview")

    if st.session_state.drive_saved:

        st.success(
            "PDF saved to Google Drive and quote registered in Google Sheet."
        )

        if st.session_state.drive_link:
            st.markdown(
                f"[Open PDF in Google Drive]({st.session_state.drive_link})"
            )

    else:
        st.warning(
            "PDF was generated, but it may not have been saved to Google Drive."
        )

    pdf_buffer = st.session_state.pdf_buffer
    quote_data = st.session_state.quote_data

    pdf_bytes = pdf_buffer.getvalue()

    pdf_doc = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    for page_number in range(len(pdf_doc)):

        page = pdf_doc.load_page(page_number)

        pix = page.get_pixmap(
            matrix=fitz.Matrix(1.5, 1.5)
        )

        img = PILImage.frombytes(
            "RGB",
            [pix.width, pix.height],
            pix.samples
        )

        st.image(
            img,
            caption=f"Page {page_number + 1}",
            use_container_width=True
        )

    file_name = (
        f"Quote - {quote_data['quote_address']}.pdf"
        .replace("/", "-")
    )

    st.download_button(
        label="Download PDF",
        data=pdf_buffer,
        file_name=file_name,
        mime="application/pdf"
    )

    st.divider()

    st.subheader("Email Quote")

    default_to = quote_data.get("client_email", "")

    default_cc = "lionelcastropalomino@gmail.com"

    default_subject = f"Quote - {quote_data['quote_address']}"

    default_message = f"""Dear {quote_data['client_name']},

Please find attached our quotation for the requested works at {quote_data['quote_address']}.

We kindly ask you to review the attached quotation at your convenience. Should you require any further information, clarification, amendments, or wish to proceed with the works, please do not hesitate to contact our team.

Thank you for considering Aaron's Demolitions. We appreciate the opportunity to provide our services and look forward to assisting you.

For more information about our company and services, please visit our website:

www.aaronsdemolitions.com.au

Kind regards,
Aaron's Rubbish Removal & Demolitions
"""

    to_email = st.text_input(
        "To",
        value=default_to
    )

    cc_email = st.text_input(
        "CC",
        value=default_cc
    )

    email_subject = st.text_input(
        "Subject",
        value=default_subject
    )

    email_message = st.text_area(
        "Message",
        value=default_message,
        height=260
    )

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
            "message": email_message
        }

        try:
            response = requests.post(
                WEB_APP_URL,
                json=email_payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()

                if result.get("status") == "OK":
                    st.success("Email sent successfully.")
                    clear_form()

                else:
                    st.error(
                        result.get(
                            "message",
                            "Email could not be sent."
                        )
                    )

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
        st.button(
            "New Quote / Clear Everything",
            on_click=clear_form
        )
