import streamlit as st

st.set_page_config(
    page_title="Aaron's Demolitions",
    layout="wide"
)

st.title("Aaron's Demolition Quote Generator")

st.subheader("Quote Information")

client_name = st.text_input("Client Name")
quote_address = st.text_input("Quote Address")
job_title = st.text_input("Job Title")

scope_text = st.text_area(
    "Inclusions & Scope of Works",
    height=200
)

exclusions_text = st.text_area(
    "Exclusions",
    height=150
)

documentation_text = st.text_area(
    "Documentation",
    height=120
)

st.subheader("Pricing")

scope1 = st.text_input("Scope 1 Description")
price1 = st.text_input("Scope 1 Price")

scope2 = st.text_input("Scope 2 Description")
price2 = st.text_input("Scope 2 Price")

scope3 = st.text_input("Scope 3 Description")
price3 = st.text_input("Scope 3 Price")

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

if st.button("Generate Quote Preview"):

    st.success("Quote preview generated successfully.")

    st.subheader("Preview")

    st.markdown(f"""
    ### Quotation: {job_title}

    **Location:** {quote_address}

    ---
    """)

    st.markdown("## Inclusions & Scope of Works")

    for line in scope_text.split("\n"):
        if line.strip():
            st.markdown(f"- {line}")

    st.markdown("## Exclusions")

    for line in exclusions_text.split("\n"):
        if line.strip():
            st.markdown(f"- {line}")

    st.markdown("## Documentation")

    for line in documentation_text.split("\n"):
        if line.strip():
            st.markdown(f"- {line}")

    st.markdown("## Scope-Based Pricing")

    st.table({
        "Scope": [
            "Scope 1",
            "Scope 2",
            "Scope 3"
        ],
        "Description": [
            scope1,
            scope2,
            scope3
        ],
        "Price": [
            price1,
            price2,
            price3
        ]
    })

    st.markdown("## Payment Terms")

    st.write(
        f"This quotation is valid for {quote_validity} from the date issued."
    )

    st.write(
        f"Deposit Required: {deposit_required}"
    )

    st.markdown("## Bank Details")

    st.write("Aaron's Rubbish Removal Pty Ltd")
    st.write("BSB: 704191")
    st.write("Account Number: 246767")
