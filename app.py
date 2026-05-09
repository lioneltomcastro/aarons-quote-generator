import streamlit as st
import io
import fitz
from PIL import Image as PILImage
from reportlab.platypus import *
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib import colors

st.set_page_config(
    page_title="Aaron's Demolition Quote Generator",
    layout="wide"
)

# =====================================================
# SESSION STATE
# =====================================================

if "show_preview" not in st.session_state:
    st.session_state.show_preview = False

if "pdf_buffer" not in st.session_state:
    st.session_state.pdf_buffer = None

if "quote_data" not in st.session_state:
    st.session_state.quote_data = {}

# =====================================================
# HELPERS
# =====================================================

def clean_lines(text):
    return [line.strip() for line in str(text).split("\n") if line.strip()]

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

def add_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(300, 38, "Aaron's Demolitions – ABN 42164569733")
    canvas.drawCentredString(300, 26, "Unit 3, 13-17 Crawford Street Braeside VIC 3195")
    canvas.drawCentredString(300, 14, "Phone: 0425 274 140 | Email: aaronsrr@gmail.com")
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

    elements.append(Paragraph(f"<b>Quote:</b> {data['quote_address']}", normal))
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

    elements.append(Paragraph(f"<b>Quotation:</b> {data['job_title']}", normal))
    elements.append(Paragraph(f"<b>Location:</b> {data['quote_address']}", normal))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Inclusions & Scope of Works", heading))
    for i, item in enumerate(clean_lines(data["scope_text"]), start=1):
        elements.append(Paragraph(f"{i}. {item}", normal))

    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Exclusions", heading))
    for i, item in enumerate(clean_lines(data["exclusions_text"]), start=1):
        elements.append(Paragraph(f"{i}. {item}", normal))

    if data["documentation_text"].strip():
        elements.append(Spacer(1, 12))
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

    validity_text = f"This quotation is valid for {data['quote_validity']} from the date issued."

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

    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)

    buffer.seek(0)
    return buffer

# =====================================================
# FORM PAGE
# =====================================================

if not st.session_state.show_preview:

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("aarons_logo.png", width=380)

    st.title("Aaron's Demolition Quote Generator")
    st.subheader("Quote Form")

    client_name = st.text_input("Client Name *")
    client_email = st.text_input("Client Email")
    quote_address = st.text_input("Quote Address *")
    job_title = st.text_input("Job Title *")

    scope_text = st.text_area("Inclusions & Scope of Works *", height=220)
    exclusions_text = st.text_area("Exclusions *", height=180)
    documentation_text = st.text_area("Documentation", height=120)

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
        ["7 days", "14 days", "21 days", "28 days", "30 days", "60 days", "90 days"]
    )

    deposit_required = st.selectbox(
        "Deposit Required",
        ["0%", "10%", "15%", "20%", "25%", "35%", "50%", "75%", "100%", "Payment upon completion"]
    )

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
            st.error("Please complete all required fields marked with *")
            st.stop()

        quote_data = {
            "client_name": client_name,
            "client_email": client_email,
            "quote_address": quote_address,
            "job_title": job_title,
            "scope_text": scope_text,
            "exclusions_text": exclusions_text,
            "documentation_text": documentation_text,
            "scope1": scope1,
            "price1": price1,
            "scope2": scope2,
            "price2": price2,
            "scope3": scope3,
            "price3": price3,
            "scope4": scope4,
            "price4": price4,
            "quote_validity": quote_validity,
            "deposit_required": deposit_required,
        }

        st.session_state.quote_data = quote_data
        st.session_state.pdf_buffer = generate_pdf(quote_data)
        st.session_state.show_preview = True
        st.rerun()

# =====================================================
# PREVIEW PAGE
# =====================================================

else:

    st.title("PDF Preview")

    pdf_buffer = st.session_state.pdf_buffer
    quote_data = st.session_state.quote_data

    pdf_bytes = pdf_buffer.getvalue()

    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for page_number in range(len(pdf_doc)):
        page = pdf_doc.load_page(page_number)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)

        st.image(
            img,
            caption=f"Page {page_number + 1}",
            use_container_width=True
        )

    file_name = f"Quote - {quote_data['quote_address']}.pdf".replace("/", "-")

    st.download_button(
        label="Download PDF",
        data=pdf_buffer,
        file_name=file_name,
        mime="application/pdf"
    )

    if st.button("Back to Edit Form"):
        st.session_state.show_preview = False
        st.rerun()
