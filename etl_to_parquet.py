import pandas as pd
import zipfile
import os
import time

ZIP_PATH = '98100403-eng.zip'
OUTPUT_PARQUET = 'education_occupation.parquet'

def run_etl():
    if not os.path.exists(ZIP_PATH):
        print(f"Error: Zip file {ZIP_PATH} not found. Please run download_and_inspect.py first.")
        return

    print("Starting ETL process...")
    start_time = time.time()
    
    # We will accumulate filtered chunks
    filtered_chunks = []
    
    with zipfile.ZipFile(ZIP_PATH) as z:
        csv_file = [name for name in z.namelist() if name.endswith('.csv')][0]
        print(f"Streaming CSV file from zip: {csv_file}")
        
        # Open the zip file stream
        with z.open(csv_file) as f:
            chunk_size = 250000
            chunk_count = 0
            total_rows_processed = 0
            
            # Read and filter CSV in chunks to keep memory usage low
            for chunk in pd.read_csv(f, chunksize=chunk_size, low_memory=False):
                chunk_count += 1
                total_rows_processed += len(chunk)
                
                # 1. Filter Geography = Canada
                # Column name: 'GEO'
                chunk_filtered = chunk[chunk['GEO'] == 'Canada']
                
                if chunk_filtered.empty:
                    continue
                
                # 2. Filter Age = Total - Age
                # Column name: 'Age (4)'
                chunk_filtered = chunk_filtered[chunk_filtered['Age (4)'] == 'Total - Age']
                
                if chunk_filtered.empty:
                    continue
                
                # 3. Clean count column: 'Statistics (6B):Count[4]'
                count_col = 'Statistics (6B):Count[4]'
                chunk_filtered[count_col] = pd.to_numeric(chunk_filtered[count_col], errors='coerce')
                
                # Drop rows with NaN or 0 count
                chunk_filtered = chunk_filtered[chunk_filtered[count_col] > 0]
                
                if chunk_filtered.empty:
                    continue
                
                # 4. Extract and rename columns
                rename_map = {
                    'Major field of study - Classification of Instructional Programs (CIP) 2021 (500)': 'fieldOfStudy',
                    'Occupation - Unit group - National Occupational Classification (NOC) 2021 (821A)': 'occupation',
                    'Highest certificate, diploma or degree (16)': 'education',
                    'Gender (3)': 'gender',
                    count_col: 'count'
                }
                
                chunk_processed = chunk_filtered[list(rename_map.keys())].rename(columns=rename_map)
                
                # 5. Append processed chunk to list
                filtered_chunks.append(chunk_processed)
                
                print(f"  Processed chunk {chunk_count}: read {total_rows_processed:,} rows, kept {len(chunk_processed):,} non-zero records")
                
    if not filtered_chunks:
        print("Error: No data matched filters.")
        return
        
    print("Concatenating filtered chunks...")
    final_df = pd.concat(filtered_chunks, ignore_index=True)
    
    # Strip whitespace from string columns
    str_cols = ['fieldOfStudy', 'occupation', 'education', 'gender']
    for col in str_cols:
        final_df[col] = final_df[col].astype(str).str.strip()
        
    print(f"Total compiled records: {len(final_df):,}")
    
    print(f"Saving to Parquet file: {OUTPUT_PARQUET}...")
    final_df.to_parquet(OUTPUT_PARQUET, index=False, compression='snappy')
    
    # Verify file is created and show its size
    parquet_size = os.path.getsize(OUTPUT_PARQUET) / (1024 * 1024)
    print(f"Parquet file saved successfully! Size: {parquet_size:.2f} MB")
    
    # Clean up the large ZIP file to reclaim space
    print(f"Cleaning up raw zip file {ZIP_PATH}...")
    try:
        os.remove(ZIP_PATH)
        print("Raw ZIP file removed successfully.")
    except Exception as e:
        print(f"Warning: Could not remove raw ZIP file: {e}")
        
    print(f"ETL completed successfully in {time.time() - start_time:.1f} seconds.")

if __name__ == '__main__':
    run_etl()
