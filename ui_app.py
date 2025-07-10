import streamlit as st
import pandas as pd
from pathlib import Path
import datetime
import io

# -------------------------------
# CONFIG
# -------------------------------
ROOT = Path(__file__).resolve().parent
TODAY = datetime.date.today().isoformat()
CSV_FILE = ROOT / f"npi_pharmacies_{TODAY}.csv"
GROUP_CSV = ROOT / "group_pharmacies.csv"

# Define the standard columns
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

    taxonomy_options = sorted(df['Healthcare Provider Taxonomy Code_1'].unique())
    selected_taxonomy = st.multiselect(
        "Select Taxonomy Codes",
        options=taxonomy_options,
        default=taxonomy_options
    )

    state_options = sorted(df['Provider Business Practice Location Address State Name'].unique())
    selected_states = st.multiselect(
        "Select States",
        options=state_options,
        default=state_options
    )

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
# Display Filtered Table
# -------------------------------
display_df = filtered_df.rename(columns=DISPLAY_LABELS)

st.subheader(f"Results: {len(display_df)} pharmacies found")
st.dataframe(display_df, use_container_width=True)

# -------------------------------
# Select Pharmacies to Add to Group
# -------------------------------
st.subheader("📌 Step 1: Select Pharmacies for Group")

selected_npis = st.multiselect(
    "Select pharmacies by NPI:",
    options=filtered_df['NPI'],
    format_func=lambda npi: f"{npi} - {filtered_df.loc[filtered_df['NPI'] == npi, 'Provider Other Organization Name_y'].values[0] if not filtered_df.loc[filtered_df['NPI'] == npi, 'Provider Other Organization Name_y'].empty else ''}"
)

# -------------------------------
# Group Details
# -------------------------------
st.subheader("📌 Step 2: Define Group Details")

group_name = st.text_input("Group Name (e.g. P305 340B Pharmacies)")
start_date = st.date_input("Start Date")
end_date = st.date_input("End Date")

# -------------------------------
# Add to Group Button
# -------------------------------
if st.button("✅ Add Selected Pharmacies to Group"):
    if not selected_npis:
        st.warning("⚠️ Please select at least one pharmacy.")
    elif not group_name.strip():
        st.warning("⚠️ Please enter a group name.")
    else:
        # Prepare new records
        new_entries = []
        for npi in selected_npis:
            pharmacy_name = filtered_df.loc[filtered_df['NPI'] == npi, 'Provider Other Organization Name_y'].values[0]
            new_entries.append({
                'Group Name': group_name.strip(),
                'NPI': npi,
                'Pharmacy Name': pharmacy_name,
                'Start Date': start_date.isoformat(),
                'End Date': end_date.isoformat()
            })

        # Load existing or create new
        try:
            existing_df = pd.read_csv(GROUP_CSV, dtype=str)
        except FileNotFoundError:
            existing_df = pd.DataFrame(columns=['Group Name', 'NPI', 'Pharmacy Name', 'Start Date', 'End Date'])

        # Append new
        updated_df = pd.concat([existing_df, pd.DataFrame(new_entries)], ignore_index=True)
        updated_df.to_csv(GROUP_CSV, index=False)

        st.success(f"✅ Added {len(new_entries)} pharmacies to group '{group_name}'.")

# -------------------------------
# View Existing Groups
# -------------------------------
st.subheader("📋 View Existing Groups")

try:
    groups_df = pd.read_csv(GROUP_CSV, dtype=str)
    if not groups_df.empty:
        st.dataframe(groups_df, use_container_width=True)

        # ⭐️ New Feature: Download CSV
        csv_data = groups_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Group Assignments CSV",
            data=csv_data,
            file_name="group_pharmacies.csv",
            mime="text/csv"
        )

        # ⭐️ New Feature: Delete Selected Rows
        st.markdown("---")
        st.subheader("🗑️ Delete Entries")
        delete_npis = st.multiselect(
            "Select entries by NPI to delete from groups:",
            options=groups_df['NPI'].unique()
        )
        if st.button("❌ Delete Selected"):
            if delete_npis:
                groups_df = groups_df[~groups_df['NPI'].isin(delete_npis)]
                groups_df.to_csv(GROUP_CSV, index=False)
                st.success(f"Deleted entries for NPIs: {', '.join(delete_npis)}")
                st.experimental_rerun()

        # ⭐️ New Feature: Edit Start/End Dates
        st.markdown("---")
        st.subheader("✏️ Edit Start/End Dates for Group Entries")
        edit_npis = st.multiselect(
            "Select NPIs to edit:",
            options=groups_df['NPI'].unique()
        )
        new_start = st.date_input("New Start Date for Selected NPIs")
        new_end = st.date_input("New End Date for Selected NPIs")
        if st.button("✏️ Apply Date Changes"):
            if edit_npis:
                groups_df.loc[groups_df['NPI'].isin(edit_npis), 'Start Date'] = new_start.isoformat()
                groups_df.loc[groups_df['NPI'].isin(edit_npis), 'End Date'] = new_end.isoformat()
                groups_df.to_csv(GROUP_CSV, index=False)
                st.success(f"Updated dates for NPIs: {', '.join(edit_npis)}")
                st.experimental_rerun()

    else:
        st.info("No groups found yet. Add some above!")
except FileNotFoundError:
    st.info("No `group_pharmacies.csv` found yet. Add a group to create it!")
