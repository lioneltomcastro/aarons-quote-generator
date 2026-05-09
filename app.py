import streamlit as st
import pandas as pd
from urllib.parse import quote

st.set_page_config(
    page_title="Aaron's Demolition Quote Generator",
    layout="wide"
)

st.image("aarons_logo.png", width=350)
st.title("Aaron's Demolition Quote Generator")

st.subheader("Quote Form")

client_name = st.text_input("Client Name *")
client_email = st.text_input("Client Email")
quote_address = st.text_input("Quote Address *")
job_title = st.text_input("Job Title *")

scope_text = st.text_area("Inclusions & Scope of Works *", height=220)
exclusions_text = st.text_area("Exclusions *", height=160)
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

generate = st.button("Generate Quote Preview")

if generate:

    if not client_name or not quote_address or not job_title or not scope_text or not exclusions_text or not scope1 or not price1:
        st.error("Please complete all required fields marked with *")
        st.stop()

    st.success("Quote preview generated successfully.")

    st.divider()
    st.header("PDF Preview")

    st.image("aarons_logo.png", width=350)

    st.markdown(f"**Quote:** {quote_address}")

    st.markdown(f"""
Thank you, **{client_name}**, for the opportunity to quote the following work. I have relied upon discussions and the information provided regarding the scope of works.

Aaron's Demolitions ensures all work will be performed within OH&S requirements and compliant with our Environment Health & Safety Management Plan. Safe Work Method Statements will be supplied upon commencement of work if required.

Aaron's Demolitions has Public Liability Insurance at $20,000,000.00, current Work Cover, operating within the Building & Construction General On-Site Award 2010, and is compliant with the National Code & Guidelines.

Please note that the term **“Dismantling”** is used instead of **“Demolition”** in order to emphasize our principles of recycling and the minimization of materials to landfills. In order to achieve this, all salvage becomes the property of Aaron's Demolitions.

Attention
""")

    st.markdown(f"### Quotation: {job_title}")
    st.markdown(f"**Location:** {quote_address}")

    st.markdown("### Inclusions & Scope of Works")
    for line in scope_text.split("\n"):
        if line.strip():
            st.markdown(f"- {line}")

    st.markdown("### Exclusions")
    for line in exclusions_text.split("\n"):
        if line.strip():
            st.markdown(f"- {line}")

    st.markdown("### Documentation")
    for line in documentation_text.split("\n"):
        if line.strip():
            st.markdown(f"- {line}")

    pricing_data = []

    if scope1.strip():
        pricing_data.append({"Scope": "Scope 1", "Description": scope1, "Price": price1})
    if scope2.strip():
        pricing_data.append({"Scope": "Scope 2", "Description": scope2, "Price": price2})
    if scope3.strip():
        pricing_data.append({"Scope": "Scope 3", "Description": scope3, "Price": price3})
    if scope4.strip():
        pricing_data.append({"Scope": "Scope 4", "Description": scope4, "Price": price4})

    st.markdown("### Scope-Based Pricing")
    st.table(pd.DataFrame(pricing_data))

    st.markdown("### Payment Terms")
    st.markdown(f"- This quotation is valid for **{quote_validity}** from the date issued.")
    st.markdown(f"- Deposit Required: **{deposit_required}**.")

    st.markdown("### Bank Details")
    st.markdown("""
**Account Name:** Aaron's Rubbish Removal Pty Ltd  
**BSB:** 704191  
**Account Number:** 246767
""")

    st.divider()

    st.subheader("Actions")

    st.info("Next step: here we connect the real PDF generator.")

    email_subject = quote(f"Quotation - {quote_address}")
    email_body = quote(f"""Hi {client_name},

Please find attached our quotation for the proposed works at {quote_address}.

Kind regards,
Aaron's Demolitions
""")

    if client_email:
        st.markdown(
            f"[Open Email Draft](mailto:{client_email}?subject={email_subject}&body={email_body})"
        )
