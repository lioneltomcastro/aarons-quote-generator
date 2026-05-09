import streamlit as st

st.set_page_config(
    page_title="Aaron's Demolitions",
    layout="wide"
)

# =========================================================
# HEADER WITH LOGO
# =========================================================

col1, col2 = st.columns([1, 4])

with col1:
    st.image("aarons_logo.png", width=180)

with col2:
    st.title("Aaron's Demolition Quote Generator")

# =========================================================
# QUOTE INFORMATION
# =========================================================

st.subheader("Quote Information")

client_name = st.text_input("Client Name *")

quote_address = st.text_input("Quote Address *")

job_title = st.text_input("Job Title *")

# =========================================================
# SCOPE SECTIONS
# =========================================================

scope_text = st.text_area(
    "Inclusions & Scope of Works",
    height=220
)

exclusions_text = st.text_area(
    "Exclusions",
    height=160
)

documentation_text = st.text_area(
    "Documentation",
    height=140
)

# =========================================================
# PRICING SECTION
# =========================================================

st.subheader("Pricing")

scope1 = st.text_input("Scope 1 Description *")
price1 = st.text_input("Scope 1 Price *")

scope2 = st.text_input("Scope 2 Description")
price2 = st.text_input("Scope 2 Price")

scope3 = st.text_input("Scope 3 Description")
price3 = st.text_input("Scope 3 Price")

# =========================================================
# TERMS
# =========================================================

quote_validity = st.selectbox(
    "Quote Validity",
    [
        "7 days",
        "14 days",
        "21 days",
        "28 days",
        "30 days"
    ]
)

deposit_required = st.selectbox(
    "Deposit Required",
    [
        "0%",
        "10%",
        "15%",
        "35%",
        "50%",
        "100%",
        "Payment upon completion"
    ]
)

st.divider()

# =========================================================
# GENERATE PREVIEW
# =========================================================

if st.button("Generate Quote Preview"):

    # =====================================================
    # REQUIRED FIELDS
    # =====================================================

    if (
        not client_name.strip()
        or not quote_address.strip()
        or not job_title.strip()
    ):

        st.error(
            "Client Name, Quote Address and Job Title are required."
        )

        st.stop()

    if (
        not scope1.strip()
        or not price1.strip()
    ):

        st.error(
            "Scope 1 Description and Scope 1 Price are required."
        )

        st.stop()

    # =====================================================
    # SUCCESS
    # =====================================================

    st.success(
        "Quote preview generated successfully."
    )

    # =====================================================
    # PREVIEW
    # =====================================================

    st.subheader("Preview")

    st.markdown(f"""
    ### Quotation: {job_title}

    **Location:** {quote_address}

    ---
    """)

    # =====================================================
    # INCLUSIONS
    # =====================================================

    st.markdown(
        "## Inclusions & Scope of Works"
    )

    for line in scope_text.split("\n"):

        if line.strip():

            st.markdown(f"- {line}")

    # =====================================================
    # EXCLUSIONS
    # =====================================================

    st.markdown("## Exclusions")

    for line in exclusions_text.split("\n"):

        if line.strip():

            st.markdown(f"- {line}")

    # =====================================================
    # DOCUMENTATION
    # =====================================================

    st.markdown("## Documentation")

    for line in documentation_text.split("\n"):

        if line.strip():

            st.markdown(f"- {line}")

    # =====================================================
    # PRICING TABLE
    # =====================================================

    st.markdown(
        "## Scope-Based Pricing"
    )

    pricing_data = []

    if scope1.strip():

        pricing_data.append({
            "Scope": "Scope 1",
            "Description": scope1,
            "Price": price1
        })

    if scope2.strip():

        pricing_data.append({
            "Scope": "Scope 2",
            "Description": scope2,
            "Price": price2
        })

    if scope3.strip():

        pricing_data.append({
            "Scope": "Scope 3",
            "Description": scope3,
            "Price": price3
        })

    st.table(pricing_data)

    # =====================================================
    # PAYMENT TERMS
    # =====================================================

    st.markdown("## Payment Terms")

    st.write(
        f"This quotation is valid for {quote_validity} from the date issued."
    )

    st.write(
        f"Deposit Required: {deposit_required}"
    )

    # =====================================================
    # BANK DETAILS
    # =====================================================

    st.markdown("## Bank Details")

    st.write(
        "Aaron's Rubbish Removal Pty Ltd"
    )

    st.write("BSB: 704191")

    st.write("Account Number: 246767")
