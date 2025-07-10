import streamlit as st
import pandas as pd
from pathlib import Path
import datetime

# -------------------------------
# CONFIG
# -------------------------------
ROOT = Path(__file__).resolve().parent
TODAY = datetime.date.today().isoformat()
CSV_FILE = ROOT / f"npi_pharmacies_{TODAY}.csv"

# Define the standard column list (must match ETL output)
STANDARD_COLUMNS = [
    'NPI',
    'Provider Organization Name (Legal Business Name)',
    'Provider Other Organization Name_y',
    'Provider First Line Business Practice Location Address',
    'Provider Second Line Business Practice Location Address',
    'Provider Business Practice Location Address City Name',
    'Provider Business Practice Location Address State Name',
    'Provider Business Practice Location Address Postal Code',
    'Healthcare Provider Taxonomy Code_1',
    'Provider License Number_1',
    'Provider License Number State Code_1'
]

# User-friendly display labels
DISPLAY_LABELS = {
    'NPI': 'NPI',
    'Provider Organization Name (Legal Business Name)': 'Provider Organization Name',
    'Provider Other Organization Name_y': 'Pharmacy Name',
    'Provider First Line Business Practice Location Address': 'First Line Address',
    'Provider Second Line Business Practice Location Address': 'Second Line Address',
    'Provider Business Practice Location Address City Name': 'City',
    'Provider Business Practice Location Address State Name': 'State',
    'Provider Business Practice Location Address Postal Code': 'Postal Code',
    'Healthcare Provider Taxonomy Code_1': 'Taxonomy Code',
    'Provider License Number_1': 'License Number',
    'Provider License Number State Code_1': 'License State'
}

# -------------------------------
# Load CSV Data
# -------------------------------
@st.cache_data
def load_data(path):
    df = pd.read_csv(path, dtype=str)
    df.fillna("", inplace=True)

    # Ensure all standard columns exist
    for col in STANDARD_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df[STANDARD_COLUMNS]

# -------------------------------
# App Start
# -------------------------------
st.set_page_config(page_title="Pharmacy Directory Viewer", layout="wide")
st.title("Pharmacy Directory Viewer")
st.markdown(f"**Data Source:** `{CSV_FILE.name}`")

if not CSV_FILE.exists():
    st.error(f"Data file not found: {CSV_FILE}")
    st.stop()

df = load_data(CSV_FILE)

# -------------------------------
# Sidebar Filters
# -------------------------------
with st.sidebar:
    st.header("Filter Pharmacies")

    # Multi-select Taxonomy Code
    taxonomy_options = sorted(df['Healthcare Provider Taxonomy Code_1'].unique())
    selected_taxonomy = st.multiselect(
        "Select Taxonomy Codes",
        options=taxonomy_options,
        default=taxonomy_options
    )

    # Multi-select States
    state_options = sorted(df['Provider Business Practice Location Address State Name'].unique())
    selected_states = st.multiselect(
        "Select States",
        options=state_options,
        default=state_options
    )

    # Free-text search
    search_term = st.text_input(
        "Search by Pharmacy Name or Organization Name",
        placeholder="Type to search..."
    )

# -------------------------------
# Apply Filters
# -------------------------------
filtered_df = df.copy()

if selected_taxonomy:
    filtered_df = filtered_df[
        filtered_df['Healthcare Provider Taxonomy Code_1'].isin(selected_taxonomy)
    ]

if selected_states:
    filtered_df = filtered_df[
        filtered_df['Provider Business Practice Location Address State Name'].isin(selected_states)
    ]

if search_term.strip():
    term = search_term.lower()
    filtered_df = filtered_df[
        filtered_df['Provider Organization Name (Legal Business Name)'].str.lower().str.contains(term)
        | filtered_df['Provider Other Organization Name_y'].str.lower().str.contains(term)
    ]

# -------------------------------
# Display Results
# -------------------------------
display_df = filtered_df.rename(columns=DISPLAY_LABELS)

st.subheader(f"Results: {len(display_df)} pharmacies found")
st.dataframe(display_df, use_container_width=True)

# -------------------------------
# Download Button
# -------------------------------
if not display_df.empty:
    csv_data = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Filtered CSV",
        data=csv_data,
        file_name=f"filtered_pharmacies_{TODAY}.csv",
        mime='text/csv'
    )
else:
    st.info("No pharmacies match the selected filters.")
