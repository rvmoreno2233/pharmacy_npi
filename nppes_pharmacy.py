import os
import shutil
import zipfile
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import pandas as pd
import datetime
import time

# ---------------------------------------------
# CONFIGURATION
# ---------------------------------------------
ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / 'input'
ARCHIVE_DIR = ROOT / 'archive'
LOGS_DIR = ROOT / 'logs'
TAXONOMY_FILE = ROOT / 'taxonomy.csv'

NPI_PFILE_DIR = INPUT_DIR / 'npi_pfile'
OTHERNAME_PFILE_DIR = INPUT_DIR / 'othername_pfile'
ARCHIVE_NPI_PFILE_DIR = ARCHIVE_DIR / 'npi_pfile'
ARCHIVE_OTHERNAME_PFILE_DIR = ARCHIVE_DIR / 'othername_pfile'

TODAY = datetime.date.today().isoformat()
OUTPUT_FILE = ROOT / f"npi_pharmacies_{TODAY}.csv"

# Define standardized column order
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

# ---------------------------------------------
# STEP 1: Download NPPES ZIP
# ---------------------------------------------
def download_nppes_zip():
    url = "https://download.cms.gov/nppes/NPI_Files.html"
    print(f"[INFO] Fetching index page: {url}")
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a')
    target_link = None
    for link in links:
        if "NPPES Data Dissemination V.2" in link.text:
            target_link = link.get('href')
            break

    if not target_link:
        raise Exception("Download link not found on CMS page.")

    full_download_url = requests.compat.urljoin(url, target_link)
    print(f"[INFO] Found download link: {full_download_url}")

    local_zip_path = ROOT / "nppes_data.zip"
    print(f"[INFO] Downloading to: {local_zip_path}")

    with requests.get(full_download_url, stream=True) as r:
        r.raise_for_status()
        with open(local_zip_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    print("[INFO] Download complete.")
    return local_zip_path

# ---------------------------------------------
# STEP 2: Unzip Contents
# ---------------------------------------------
def unzip_file(zip_path):
    dest = ROOT / "unzipped"
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(dest)
    print(f"[INFO] Unzipped to: {dest}")

# ---------------------------------------------
# STEP 3: Move Files to Input Directories
# ---------------------------------------------
def move_files():
    unzipped_dir = ROOT / 'unzipped'
    NPI_PFILE_DIR.mkdir(parents=True, exist_ok=True)
    OTHERNAME_PFILE_DIR.mkdir(parents=True, exist_ok=True)

    for file in unzipped_dir.rglob('*.csv'):
        fname = file.name.lower()

        if fname.endswith('_fileheader.csv'):
            print(f"[INFO] Skipping header file: {file}")
            continue

        if fname.startswith('npidata_pfile'):
            dest = NPI_PFILE_DIR / file.name
            print(f"[INFO] Moving NPI file: {file} -> {dest}")
            shutil.move(str(file), str(dest))

        elif fname.startswith('othername_pfile'):
            dest = OTHERNAME_PFILE_DIR / file.name
            print(f"[INFO] Moving OTHERNAME file: {file} -> {dest}")
            shutil.move(str(file), str(dest))

    print("[INFO] Files moved to input directories.")

# ---------------------------------------------
# STEP 4: Filter NPI File
# ---------------------------------------------
def filter_npi_file(npi_file_path, taxonomy_file_path):
    print(f"[INFO] Filtering NPI file: {npi_file_path}")
    taxonomy_df = pd.read_csv(taxonomy_file_path, dtype=str)
    taxonomy_codes = set(taxonomy_df['Taxonomy Code'].dropna())

    chunksize = 500000
    filtered_chunks = []

    for chunk in pd.read_csv(npi_file_path, chunksize=chunksize, dtype=str):
        chunk.fillna("", inplace=True)

        # 1. Entity Type Code = 2
        before_entity = len(chunk)
        chunk = chunk[chunk['Entity Type Code'] == '2']
        print(f"[DEBUG] Entity Type filter removed {before_entity - len(chunk)} rows")

        # 2. NPI Deactivation Date is empty
        before_deactivation = len(chunk)
        chunk = chunk[chunk['NPI Deactivation Date'].str.strip() == ""]
        print(f"[DEBUG] Deactivation filter removed {before_deactivation - len(chunk)} rows")

        # 3. Taxonomy code match
        before_taxonomy = len(chunk)
        chunk = chunk[chunk['Healthcare Provider Taxonomy Code_1'].isin(taxonomy_codes)]
        print(f"[DEBUG] Taxonomy filter removed {before_taxonomy - len(chunk)} rows")

        if not chunk.empty:
            filtered_chunks.append(chunk)

    if filtered_chunks:
        filtered_df = pd.concat(filtered_chunks, ignore_index=True)
        print(f"[INFO] Filtered total rows: {len(filtered_df)}")
        return filtered_df
    else:
        print("[WARN] No rows matched filters.")
        return pd.DataFrame(columns=STANDARD_COLUMNS)

# ---------------------------------------------
# STEP 5: Merge with OTHERNAME
# ---------------------------------------------
def merge_othername(filtered_df, othername_file_path):
    print(f"[INFO] Merging with OTHERNAME file: {othername_file_path}")
    othername_df = pd.read_csv(othername_file_path, dtype=str)
    othername_df.fillna("", inplace=True)

    merged = pd.merge(
        filtered_df,
        othername_df[['NPI', 'Provider Other Organization Name']],
        on='NPI',
        how='left'
    )

    # Rename to _y suffix explicitly
    merged = merged.rename(columns={
        'Provider Other Organization Name': 'Provider Other Organization Name_y'
    })

    # Ensure standard columns exist
    for col in STANDARD_COLUMNS:
        if col not in merged.columns:
            merged[col] = ""

    merged = merged[STANDARD_COLUMNS]
    return merged

# ---------------------------------------------
# STEP 6: Archive Originals
# ---------------------------------------------
def archive_input_files():
    ARCHIVE_NPI_PFILE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_OTHERNAME_PFILE_DIR.mkdir(parents=True, exist_ok=True)

    for dirpath in [NPI_PFILE_DIR, OTHERNAME_PFILE_DIR]:
        for file in dirpath.iterdir():
            if 'npidata_pfile' in file.name.lower():
                shutil.move(str(file), str(ARCHIVE_NPI_PFILE_DIR / file.name))
            elif 'othername_pfile' in file.name.lower():
                shutil.move(str(file), str(ARCHIVE_OTHERNAME_PFILE_DIR / file.name))
    print("[INFO] Archived processed input files.")

# ---------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------
def main():
    try:
        zip_path = download_nppes_zip()
        print("[INFO] Waiting 40 seconds for large download assurance...")
        time.sleep(40)

        unzip_file(zip_path)
        move_files()

        # Detect input files
        npi_files = list(NPI_PFILE_DIR.glob('npidata_pfile*.csv'))
        othername_files = list(OTHERNAME_PFILE_DIR.glob('othername_pfile*.csv'))
        if not npi_files or not othername_files:
            raise Exception("Required input files not found after move.")

        npi_file = npi_files[0]
        othername_file = othername_files[0]

        # Process
        filtered_npi_df = filter_npi_file(npi_file, TAXONOMY_FILE)
        if filtered_npi_df.empty:
            print("[WARN] No matching rows to save. Exiting.")
            return

        final_df = merge_othername(filtered_npi_df, othername_file)
        final_df.to_csv(OUTPUT_FILE, index=False)
        print(f"[SUCCESS] Saved final output: {OUTPUT_FILE}")

        archive_input_files()

        # Cleanup
        zip_path.unlink(missing_ok=True)
        shutil.rmtree(ROOT / 'unzipped', ignore_errors=True)
        print("[INFO] Processing complete.")

    except Exception as e:
        print(f"[ERROR] {e}")

# ---------------------------------------------
# ENTRY POINT
# ---------------------------------------------
if __name__ == "__main__":
    main()
