import streamlit as st
import pandas as pd
import re
from io import BytesIO
from openpyxl import load_workbook

#streamlit App Title
st.title("Radiologist Monthly Pay Processor")

#file Upload Section
uploaded_file = st.file_uploader("Upload the Excel file", type=["xlsx"])

if uploaded_file:
    #load the file into a BytesIO object
    file_bytes = BytesIO(uploaded_file.read())

    #load the data from the uploaded file
    df_raw = pd.read_excel(file_bytes, sheet_name='RTAT by Radiologist', header=None)

    #extract Date Range
    header_block = str(df_raw.iloc[0, 0])
    date_match = re.search(r'Date Range:\s*([\d-]+)\s*-\s*([\d-]+)', header_block)
    date_range = f"{date_match.group(1)}_to_{date_match.group(2)}" if date_match else "DateRangeNotFound"

    #extract Radiologist Name
    radiologist_name = df_raw.iloc[4, 0]
    safe_radiologist_name = radiologist_name.replace(",", "").replace(" ", "_")

    #extract Exam List
    exam_series = df_raw.iloc[5:, 4].dropna().astype(str)
    exam_list = [exam for exam in exam_series.tolist() if not exam.strip().lower().startswith('total')]
    df_flat = pd.DataFrame({'Exam': exam_list})

    #categorization Logic
    category_map = {
        "CT AP": [r"abd[\s/-]*pel", r"abdomen[\s/-]*pelvis", r"stone[\s/-]*protocol", r"hematuria"],
        "CT CAP": [r"chest[\s,/-]*abd[\s,/-]*pelvis"],
        "CT": [r"\bct\b"],
        "MR": [r"\bmri\b", r"\bmr\b"],
        "US": [r"\bus\b", r"ultrasound"],
        "xray": [r"\bx[-]?ray\b", r"\bxr\b"],
        "CTA/CTV": [r"\bcta\b", r"\bctv\b"]
    }

    def categorize_exam(exam_name):
        exam_name_lower = exam_name.lower()
        for category, patterns in category_map.items():
            for pattern in patterns:
                if re.search(pattern, exam_name_lower, re.IGNORECASE):
                    return category
        return "Uncategorized"

    df_flat['Category'] = df_flat['Exam'].apply(categorize_exam)

    #payment Calculation
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

    summary = df_flat['Category'].value_counts().reset_index()
    summary.columns = ['Category', 'Count']
    summary['Rate'] = summary['Category'].map(rate_table)
    summary['Total Pay'] = summary['Count'] * summary['Rate']

    #add Total Row
    total_row = pd.DataFrame({
        'Category': ['TOTAL'],
        'Count': [summary['Count'].sum()],
        'Rate': [''],
        'Total Pay': [summary['Total Pay'].sum()]
    })
    summary_with_total = pd.concat([summary, total_row], ignore_index=True)

    #format Dollar Signs
    summary_with_total['Rate'] = summary_with_total['Rate'].apply(lambda x: f"${int(x)}" if isinstance(x, (int, float)) else '')
    summary_with_total['Total Pay'] = summary_with_total['Total Pay'].apply(lambda x: f"${x:,.2f}" if isinstance(x, (int, float)) else x)

    #display Results
    st.markdown("### Summary Table")
    st.dataframe(summary_with_total)

    grand_total = summary_with_total.iloc[-1]['Total Pay']
    st.markdown(f"## Grand Total: {grand_total}")

    #append New Sheets to the Uploaded File
    file_bytes.seek(0)
    with pd.ExcelWriter(file_bytes, engine='openpyxl', mode='a') as writer:
        summary_with_total.to_excel(writer, sheet_name='Pay Summary', index=False)
        df_flat.to_excel(writer, sheet_name='Detailed Exams', index=False)

    #provide Download Link
    st.download_button(
        label="Download Updated Excel File",
        data=file_bytes.getvalue(),
        file_name=uploaded_file.name,
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
