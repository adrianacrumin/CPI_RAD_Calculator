import streamlit as st
import pandas as pd
import re
from io import BytesIO
from openpyxl import load_workbook

# Streamlit App Title
st.title("Radiologist Monthly Pay Processor")

# File Upload Section
uploaded_file = st.file_uploader("Upload the Excel file", type=["xlsx"])

if uploaded_file:
    file_bytes = BytesIO(uploaded_file.read())

    # Load the data
    df_raw = pd.read_excel(file_bytes, sheet_name='Signed Studies with CPT', header=None)

    # Use correct header row (row 2) and data from row 3 onward
    df_data = df_raw.iloc[3:].copy()
    df_data.columns = df_raw.iloc[2].str.strip()  # Clean headers

    # Select relevant columns
    df_exams = df_data[['Radiologist', 'Exam Description', 'Modality Type Code']].dropna(subset=['Exam Description'])
    df_exams.columns = ['Radiologist', 'Exam', 'Modality']  # Rename for convenience

    # --- Categorization by Exam Description ---
    category_map = {
        "CT AP": [r"abd[\s/-]*pel", r"abdomen[\s/-]*pelvis", r"stone[\s/-]*protocol", r"hematuria"],
        "CT CAP": [r"chest[\s,/-]*abd[\s,/-]*pelvis", r"\bcap\b"],
        "CT": [r"\bct\b"],
        "CTA/CTV": [r"\bcta\b", r"\bctv\b"],
        "MR": [r"\bmri\b", r"\bmr\b", r"\bmra\b", r"\bmrv\b", r"mra/mrv", r"mra[\s/-]*brain", r"mra[\s/-]*neck"],
        "US": [r"\bus\b", r"ultrasound"],
        "xray": [r"\bx[-]?ray\b", r"\bxr\b", r"\bdr\b", r"\bcomplete\b"]
    }

    def categorize_exam(exam_name):
        exam_name_lower = str(exam_name).lower()
        for category, patterns in category_map.items():
            for pattern in patterns:
                if re.search(pattern, exam_name_lower):
                    return category
        return "Uncategorized"

    df_exams['Category'] = df_exams['Exam'].apply(categorize_exam)

    # --- Fallback: Categorize by Modality Code if still Uncategorized ---
    modality_fallback = {
        "ct": "CT",
        "cta": "CTA/CTV",
        "ctv": "CTA/CTV",
        "mr": "MR",
        "mra": "MR",
        "mrv": "MR",
        "us": "US",
        "dr": "xray",
        "cr": "xray",
        "xr": "xray",
        "xry": "xray"
    }

    df_exams['Category'] = df_exams.apply(
        lambda row: modality_fallback.get(str(row['Modality']).strip().lower(), row['Category'])
        if row['Category'] == "Uncategorized" else row['Category'],
        axis=1
    )

    # --- Pay Rate Logic ---
    rate_table = {
        "MR": 63,
        "CT": 45,
        "CTA/CTV": 50,
        "CT CAP": 95,
        "CT AP": 50,
        "US": 26,
        "xray": 10,
        "Uncategorized": 0
    }

    # Summary Table
    summary = df_exams['Category'].value_counts().reset_index()
    summary.columns = ['Category', 'Count']
    summary['Rate'] = summary['Category'].map(rate_table)
    summary['Total Pay'] = summary['Count'] * summary['Rate']

    # Add Total Row
    total_row = pd.DataFrame({
        'Category': ['TOTAL'],
        'Count': [summary['Count'].sum()],
        'Rate': [''],
        'Total Pay': [summary['Total Pay'].sum()]
    })
    summary_with_total = pd.concat([summary, total_row], ignore_index=True)

    # Format Dollars
    summary_with_total['Rate'] = summary_with_total['Rate'].apply(lambda x: f"${int(x)}" if isinstance(x, (int, float)) else '')
    summary_with_total['Total Pay'] = summary_with_total['Total Pay'].apply(lambda x: f"${x:,.2f}" if isinstance(x, (int, float)) else x)

    # Display Results
    st.markdown("### Summary Table")
    st.dataframe(summary_with_total)

    grand_total = summary_with_total.iloc[-1]['Total Pay']
    st.markdown(f"## Grand Total: {grand_total}")

    # Append new sheets and allow download
    file_bytes.seek(0)
    with pd.ExcelWriter(file_bytes, engine='openpyxl', mode='a') as writer:
        summary_with_total.to_excel(writer, sheet_name='Pay Summary', index=False)
        df_exams.to_excel(writer, sheet_name='Detailed Exams', index=False)

    st.download_button(
        label="Download Updated Excel File",
        data=file_bytes.getvalue(),
        file_name=uploaded_file.name,
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
