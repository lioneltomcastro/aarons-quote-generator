import streamlit as st
import pandas as pd
import io
from urllib.parse import quote

from reportlab.platypus import *
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib import colors

import fitz
from PIL import Image as PILImage

# =====================================================
# PAGE CONFIG
# =====================================================

st.set_page_config(
    page_title="Aaron's Demolition Quote Generator",
    layout="wide"
)

# =====================================================
# HEADER
# =====================================================

col1, col2, col3 = st.columns([1,2,1])

with col2:
    st.image("aarons_logo.png", width=380)

st.title("Aaron's Demolition Quote Generator")

# =====================================================
# FORM
# =====================================================

client_name = st.text_input("Client Name *")
client_email = st.text_input("Client Email")
quote_address = st.text_input("Quote Address *")
job_title = st.text_input("Job Title *")

scope_text = st.text_area(
    "Inclusions & Scope of Works *",
    height=220
)

exclusions_text = st.text_area(
    "Exclusions *",
    height=180
)

documentation_text = st.text_area(
    "Documentation",
    height=120
)

st.subheader("Scope-Based Pricing")

scope1 = st.text_input("Scope 1 Description *")
price1 = st.text_input("Scope 1 Price *")

scope2 = st.text_input("Scope 2 Description")
price2 = st.text_input("Scope 2 Price")

scope3 = st.text_input("Scope 3 Description")
price3 = st.text_input("Scope 3 Price")

scope4 = st.text_input("Scope 4 Description")
price4 = st.text_input("Scope 4 Price")

quote_validity = st.selectbox(
    "Quote Validity",
    [
        "7 days",
        "14 days",
        "21 days",
        "28 days",
        "30 days",
        "60 days",
        "90 days"
    ]
)

deposit_required = st.selectbox(
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
    ]
)

# =====================================================
# HELPERS
# =====================================================

def clean_lines(text):
    return [
        line.strip()
        for line in str(text).split("\n")
        if line.strip()
    ]

def payment_text(deposit):

    if deposit == "100%":
        return (
            "Full payment upfront is required prior to commencement of works."
        )

    if deposit == "Payment upon completion":
        return (
            "Payment is to be made upon completion of works unless negotiated otherwise at the time of contract."
        )

    if deposit == "0%":
        return (
            "No upfront deposit is required. The balance is to be paid upon completion of works."
        )

    return (
        f"Strictly {deposit} upfront deposit is required to secure and schedule the booking. "
        f"The remaining balance is to be paid upon completion of works unless negotiated otherwise."
    )

# =====================================================
# FOOTER
# =====================================================

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

# =====================================================
# PDF GENERATOR
# =====================================================

def generate_pdf():

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

    # =====================================================
    # LOGO
    # =====================================================

    logo = Image(
        "aarons_logo.png",
        width=300,
        height=120
    )

    logo.hAlign = "CENTER"

    elements.append(logo)
    elements.append(Spacer(1, 45))

    # =====================================================
    # INTRO
    # =====================================================

    elements.append(
        Paragraph(
            f"<b>Quote:</b> {quote_address}",
            normal
        )
    )

    elements.append(Spacer(1, 10))

    intro = f"""
    Thank you, {client_name}, for the opportunity to quote the following work. I have relied upon discussions and the information provided regarding the scope of works.

    <br/><br/>

    Aaron's Demolitions ensures all work will be performed within OH&S requirements and compliant with our Environment Health & Safety Management Plan. Safe Work Method Statements will be supplied upon commencement of work if required.

    <br/><br/>

    Aaron's Demolitions has Public Liability Insurance at $20,000,000.00, current Work Cover, operating within the Building & Construction General On-Site Award 2010, and is compliant with the National Code & Guidelines.

    <br/><br/>

    Please note that the term “Dismantling” is used instead of “Demolition” in order to emphasize our principles of recycling and the minimization of materials to landfills. In order to achieve this, all salvage becomes the property of Aaron's Demolitions.

    <br/><br/>

    Attention
    """

    elements.append(
        Paragraph(
            intro,
            normal
        )
    )

    elements.append(PageBreak())

    # =====================================================
    # PROJECT DETAILS
    # =====================================================

    elements.append(
        Paragraph(
            f"<b>Quotation:</b> {job_title}",
            normal
        )
    )

    elements.append(
        Paragraph(
            f"<b>Location:</b> {quote_address}",
            normal
        )
    )

    elements.append(Spacer(1, 12))

    # =====================================================
    # INCLUSIONS
    # =====================================================

    elements.append(
        Paragraph(
            "Inclusions & Scope of Works",
            heading
        )
    )

    for i, item in enumerate(clean_lines(scope_text), start=1):

        elements.append(
            Paragraph(
                f"{i}. {item}",
                normal
            )
        )

    elements.append(Spacer(1, 12))

    # =====================================================
    # EXCLUSIONS
    # =====================================================

    elements.append(
        Paragraph(
            "Exclusions",
            heading
        )
    )

    for i, item in enumerate(clean_lines(exclusions_text), start=1):

        elements.append(
            Paragraph(
                f"{i}. {item}",
                normal
            )
        )

    elements.append(Spacer(1, 12))

    # =====================================================
    # DOCUMENTATION
    # =====================================================

    if documentation_text.strip():

        elements.append(
            Paragraph(
                "Documentation",
                heading
            )
        )

        for i, item in enumerate(clean_lines(documentation_text), start=1):

            elements.append(
                Paragraph(
                    f"{i}. {item}",
                    normal
                )
            )

    elements.append(Spacer(1, 18))

    # =====================================================
    # PRICING TABLE
    # =====================================================

    pricing_rows = []

    if scope1.strip():
        pricing_rows.append([
            "Scope 1",
            Paragraph(scope1, table_text),
            Paragraph(price1, table_text)
        ])

    if scope2.strip():
        pricing_rows.append([
            "Scope 2",
            Paragraph(scope2, table_text),
            Paragraph(price2, table_text)
        ])

    if scope3.strip():
        pricing_rows.append([
            "Scope 3",
            Paragraph(scope3, table_text),
            Paragraph(price3, table_text)
        ])

    if scope4.strip():
        pricing_rows.append([
            "Scope 4",
            Paragraph(scope4, table_text),
            Paragraph(price4, table_text)
        ])

    pricing_block = []

    pricing_block.append(
        Paragraph(
            "Scope-Based Pricing",
            heading
        )
    )

    table_data = [
        ["Scope", "Description", "Price"]
    ] + pricing_rows

    pricing_table = Table(
        table_data,
        colWidths=[70, 320, 110],
        repeatRows=1
    )

    pricing_table.setStyle(TableStyle([

        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),

        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),

        ("FONTSIZE", (0,0), (-1,-1), 9),

        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),

        ("VALIGN", (0,0), (-1,-1), "TOP"),

        ("ALIGN", (0,0), (0,-1), "CENTER"),

        ("ALIGN", (2,1), (2,-1), "CENTER"),

        ("LEFTPADDING", (0,0), (-1,-1), 6),

        ("RIGHTPADDING", (0,0), (-1,-1), 6),

        ("TOPPADDING", (0,0), (-1,-1), 8),

        ("BOTTOMPADDING", (0,0), (-1,-1), 8),

    ]))

    pricing_block.append(pricing_table)
    pricing_block.append(Spacer(1, 14))

    validity_text = (
        f"This quotation is valid for {quote_validity} from the date issued."
    )

    pricing_block.append(
        Paragraph(
            validity_text,
            normal
        )
    )

    pricing_block.append(
        Paragraph(
            payment_text(deposit_required),
            normal
        )
    )

    pricing_block.append(Spacer(1, 10))

    bank_details = """
    <b>Bank Details</b><br/>
    Account Name: Aaron's Rubbish Removal Pty Ltd<br/>
    BSB: 704191<br/>
    Account Number: 246767
    """

    pricing_block.append(
        Paragraph(
            bank_details,
            normal
        )
    )

    elements.append(
        KeepTogether(pricing_block)
    )

    # =====================================================
    # BUILD PDF
    # =====================================================

    doc.build(
        elements,
        onFirstPage=add_footer,
        onLaterPages=add_footer
    )

    buffer.seek(0)

    return buffer

# =====================================================
# GENERATE BUTTON
# =====================================================

if st.button("Generate Formal PDF Preview"):

    if (
        not client_name
        or not quote_address
        or not job_title
        or not scope_text
        or not exclusions_text
        or not scope1
        or not price1
    ):

        st.error(
            "Please complete all required fields marked with *"
        )

        st.stop()

    pdf_buffer = generate_pdf()

    st.success("Formal PDF generated successfully.")

    # =====================================================
    # PDF PREVIEW
    # =====================================================

    st.subheader("PDF Preview")

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

    # =====================================================
    # DOWNLOAD BUTTON
    # =====================================================

    file_name = (
        f"Quote - {quote_address}.pdf"
        .replace("/", "-")
    )

    st.download_button(
        label="Download PDF",
        data=pdf_buffer,
        file_name=file_name,
        mime="application/pdf"
    )
