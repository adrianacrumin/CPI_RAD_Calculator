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
        "CT CAP": [r"ct[\s/-]*chest[\s/-]*abd[\s/-]*pelvis", r"ct[\s/-]*cap", r"\bct\s*chest\s*abd\s*pelvis\b", r"\bcap\b"],
        "CT AP": [r"ct[\s/-]*abd[\s/-]*pel", r"ct[\s/-]*stone[\s/-]*protocol", r"ct[\s/-]*hematuria", r"abdomen[\s/-]*pelvis"],
        "CTA/CTV": [r"\bcta\b", r"\bctv\b"],
        "MR": [r"\bmri\b", r"\bmr\b", r"\bmra\b", r"\bmrv\b", r"mra/mrv", r"mra[\s/-]*brain", r"mra[\s/-]*neck"],
        "US": [r"\bus\b", r"ultrasound"],
        "xray": [r"\bx[-]?ray\b", r"\bxr\b", r"\bdr\b", r"\bcr\b", r"\bxry\b", r"\bcomplete\b"],
        "CT": [r"\bct\b"]
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

    # --- Pay Rate Tables by Radiologist ---
    rate_tables = {
        "Ghitis": {
            "MR": 70,
            "CT": 50,
            "CTA/CTV": 60,
            "CT AP": 70,
            "CT CAP": 120,
            "US": 25,
            "xray": 0,
            "Uncategorized": 0
        },
        "Park": {
            "MR": 63,
            "CT": 45,
            "CTA/CTV": 50,
            "CT AP": 50,
            "CT CAP": 95,
            "US": 26,
            "xray": 10,
            "Uncategorized": 0
        }
    }

    def get_rate(row):
        doc = str(row['Radiologist']).strip()
        category = row['Category']
        for name, table in rate_tables.items():
            if name.lower() in doc.lower():
                return table.get(category, 0)
        return 0  # Default if doctor not found

    df_exams['Rate'] = df_exams.apply(get_rate, axis=1)
    df_exams['Total Pay'] = df_exams['Rate'] * 1  # Each row = 1 exam

    # --- Summary by Radiologist & Category ---
    summary = df_exams.groupby(['Radiologist', 'Category']).agg(
        Count=('Category', 'size'),
        Rate=('Rate', 'first'),
        Total_Pay=('Total Pay', 'sum')
    ).reset_index()

    # Add TOTAL Row per Radiologist
    totals = summary.groupby('Radiologist').agg(
        Count=('Count', 'sum'),
        Rate=('Rate', lambda x: ''),  # Blank for total
        Total_Pay=('Total_Pay', 'sum')
    ).reset_index()
    totals['Category'] = 'TOTAL'

    summary_with_total = pd.concat([summary, totals], ignore_index=True)

    # Format $
    summary_with_total['Rate'] = summary_with_total['Rate'].apply(lambda x: f"${x}" if isinstance(x, (int, float)) else '')
    summary_with_total['Total_Pay'] = summary_with_total['Total_Pay'].apply(lambda x: f"${x:,.2f}" if isinstance(x, (int, float)) else x)

    # Display Results
    st.markdown("### Summary Table")
    st.dataframe(summary_with_total)

    overall_total = df_exams['Total Pay'].sum()
    st.markdown(f"## Grand Total for All Radiologists: ${overall_total:,.2f}")

    # Save Output Back to Excel
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
