import pandas as pd
from azure.storage.blob import ContainerClient
from io import BytesIO
import sys
from collections import defaultdict

# CONFIGURATION - Update these values for your environment

CONFIG = {
    # Azure Storage SAS URL (required)
    'AZURE_SAS_URL': '',
    
    # Base path in container
    'LEVEL2_PATH': '2024_ciac_selectlinkanalysis/results',
    
    # MPO names (comma-separated)
    'MPO_LIST': 'abilene,amarillo,austin,bcs,beaumont,corpuschristi,dfw,elpaso,gatesville,houston,kt,laredo,longview,lubbock,permianbasin,rgv,sanangelo,sanantonio,shermandenison,texarkana,tyler,victoria,waco,wichitafalls',
    
    # Years to analyze
    'YEARS': '2019,2021,2022,2023,2024',
    
    # Parquet file columns
    'WEIGHT_CLASS_COLUMN': 'vehicle_weight_class',
    'COUNT_COLUMN': 'count',
    
    # Folder name containing parquet files
    'TRIP_FOLDER': 'range_ring',
    
    # Output files
    'OUTPUT_EXCEL': 'MPO_Road_Trip_Analysis.xlsx',
    'OUTPUT_MISSING_CSV': 'MPO_Missing_Data_List.csv'
}

def load_config():
    mpo_list = [m.strip() for m in CONFIG['MPO_LIST'].split(',') if m.strip()]
    years_list = [y.strip() for y in CONFIG['YEARS'].split(',') if y.strip()]
    
    if not CONFIG['AZURE_SAS_URL'] or 'yourstorageaccount' in CONFIG['AZURE_SAS_URL']:
        print("ERROR: Update AZURE_SAS_URL in CONFIG section")
        sys.exit(1)
    
    return {
        'AZURE_SAS_URL': CONFIG['AZURE_SAS_URL'],
        'LEVEL2_PATH': CONFIG['LEVEL2_PATH'].rstrip('/'),
        'MPO_LIST': mpo_list,
        'YEARS': years_list,
        'TRIP_FOLDER': CONFIG['TRIP_FOLDER'],
        'WEIGHT_CLASS_COLUMN': CONFIG['WEIGHT_CLASS_COLUMN'],
        'COUNT_COLUMN': CONFIG['COUNT_COLUMN'],
        'OUTPUT_EXCEL': CONFIG['OUTPUT_EXCEL'],
        'OUTPUT_MISSING_CSV': CONFIG['OUTPUT_MISSING_CSV']
    }

def create_excel_report(results, mpo_list, years, weight_classes, output_file):
    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        workbook = writer.book
        
        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#4472C4', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter'
        })
        
        subheader_format = workbook.add_format({
            'bold': True, 'bg_color': '#B4C7E7', 'border': 1, 'align': 'center'
        })
        
        number_format = workbook.add_format({
            'num_format': '#,##0', 'border': 1, 'align': 'right'
        })
        
        road_format = workbook.add_format({'border': 1, 'align': 'center'})
        
        total_format = workbook.add_format({
            'bold': True, 'bg_color': '#F4B084', 'num_format': '#,##0',
            'border': 1, 'align': 'right'
        })
        
        summary_data = []
        for mpo in mpo_list:
            row = {'MPO': mpo}
            for year in years:
                total = sum(
                    sum(results.get(mpo, {}).get(road, {}).get(year, {}).values())
                    for road in results.get(mpo, {}).keys()
                )
                row[year] = total
            row['Total'] = sum(row[y] for y in years)
            summary_data.append(row)
        
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name='Summary', index=False)
        
        worksheet = writer.sheets['Summary']
        worksheet.set_column('A:A', 30)
        for i in range(len(years) + 1):
            worksheet.set_column(i+1, i+1, 15)
        
        for col_num, value in enumerate(df_summary.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        for row_num in range(len(df_summary)):
            for col_num in range(1, len(df_summary.columns)):
                worksheet.write(row_num + 1, col_num, df_summary.iloc[row_num, col_num], number_format)

        for mpo in mpo_list:
            if mpo not in results or not results[mpo]:
                continue
            
            worksheet = workbook.add_worksheet(mpo[:31])
            
            worksheet.write(0, 0, 'Road ID', header_format)
            col = 1
            for year in years:
                merge_end = col + len(weight_classes) - 1
                worksheet.merge_range(0, col, 0, merge_end, year, header_format)
                col = merge_end + 1
            
            col = 1
            for year in years:
                for wc in weight_classes:
                    worksheet.write(1, col, f"Weight Class {wc}", subheader_format)
                    col += 1
            
            worksheet.set_column(0, 0, 15)
            for i in range(1, 1 + len(years) * len(weight_classes)):
                worksheet.set_column(i, i, 12)
            
            road_ids = sorted(results[mpo].keys(), 
                            key=lambda x: (x.replace('.', '').replace('-', '').replace('_', '').isdigit() and 
                                         int(x.replace('.', '').replace('-', '').replace('_', '')) or float('inf'), x))
            
            year_totals = {year: {wc: 0 for wc in weight_classes} for year in years}
            
            row_num = 2
            for road_id in road_ids:
                worksheet.write(row_num, 0, road_id, road_format)
                col = 1
                
                for year in years:
                    year_data = results[mpo][road_id].get(year, {})
                    for wc in weight_classes:
                        count = year_data.get(wc, 0)
                        worksheet.write(row_num, col, count, number_format)
                        year_totals[year][wc] += count
                        col += 1
                
                row_num += 1
            
            worksheet.write(row_num, 0, 'TOTAL', total_format)
            col = 1
            for year in years:
                for wc in weight_classes:
                    worksheet.write(row_num, col, year_totals[year][wc], total_format)
                    col += 1

def generate_missing_data_report(excel_file, mpo_list, years, weight_classes, output_csv):
    missing_data = []
    
    for mpo in mpo_list:
        try:
            df = pd.read_excel(excel_file, sheet_name=mpo[:31], header=[0, 1])
            df = df[df.iloc[:, 0] != 'TOTAL']
            
            if len(df) == 0:
                continue
            
            road_ids = df.iloc[:, 0].values
            
            for idx, road_id in enumerate(road_ids):
                for year_idx, year in enumerate(years):
                    start_col = 1 + (year_idx * len(weight_classes))
                    end_col = start_col + len(weight_classes)
                    year_values = df.iloc[idx, start_col:end_col].values
                    
                    if all(v == 0 or pd.isna(v) for v in year_values):
                        missing_data.append({
                            'Year': year,
                            'MPO': mpo,
                            'Road ID': road_id
                        })
        except Exception:
            continue
    
    if missing_data:
        df_missing = pd.DataFrame(missing_data)
        df_missing.to_csv(output_csv, index=False)
    
    return len(missing_data)

def main():
    config = load_config()
    
    print("="*60)
    print("MPO ROAD TRIP ANALYSIS BY WEIGHT CLASS")
    print("="*60)
    
    try:
        print("\nConnecting to Azure Storage...")
        container_client = ContainerClient.from_container_url(config['AZURE_SAS_URL'])
        print("Connected")
        
        print(f"\nMPOs: {len(config['MPO_LIST'])}")
        print(f"Years: {', '.join(config['YEARS'])}")
        
        print("\n" + "="*60)
        print("PROCESSING MPOs")
        print("="*60)
        
        all_weight_classes = set()
        results = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
        
        for mpo_idx, mpo in enumerate(config['MPO_LIST'], 1):
            print(f"\n[{mpo_idx}/{len(config['MPO_LIST'])}] {mpo}")
            
            mpo_path = f"{config['LEVEL2_PATH']}/{mpo}/".replace('//', '/')
            
            all_mpo_blobs = {}
            road_ids = set()
            
            for blob in container_client.list_blobs(name_starts_with=mpo_path):
                if not blob.name.endswith('.parquet') or f"/{config['TRIP_FOLDER']}/" not in blob.name:
                    continue
                
                relative = blob.name.replace(mpo_path, '').lstrip('/')
                parts = relative.split('/')
                
                if len(parts) >= 4:
                    road_id = parts[0]
                    year = parts[1]
                    
                    if year in ['2023', '2024'] and len(parts) >= 5:
                        intermediate = parts[2]
                        folder = parts[3]
                        if intermediate == 'annual' and folder == config['TRIP_FOLDER'] and year in config['YEARS']:
                            road_ids.add(road_id)
                            all_mpo_blobs[blob.name] = (road_id, year)
                    
                    elif year not in ['2023', '2024']:
                        folder = parts[2]
                        if folder == config['TRIP_FOLDER'] and year in config['YEARS']:
                            road_ids.add(road_id)
                            all_mpo_blobs[blob.name] = (road_id, year)
            
            road_ids = sorted(road_ids, 
                            key=lambda x: (x.replace('.', '').replace('-', '').replace('_', '').isdigit() and 
                                         int(x.replace('.', '').replace('-', '').replace('_', '')) or float('inf'), x))
            
            print(f"  {len(road_ids)} roads, {len(all_mpo_blobs)} files")
            
            if not road_ids:
                continue
            
            for road_idx, road_id in enumerate(road_ids, 1):
                print(f"    [{road_idx}/{len(road_ids)}] {road_id}", end=' ', flush=True)
                
                road_has_data = False
                for year in config['YEARS']:
                    year_files = [path for path, (rid, yr) in all_mpo_blobs.items() 
                                 if rid == road_id and yr == year]
                    
                    if not year_files:
                        results[mpo][road_id][year] = {}
                        continue
                    
                    counts = defaultdict(int)
                    for file_path in year_files:
                        try:
                            blob_client = container_client.get_blob_client(file_path)
                            blob_data = blob_client.download_blob().readall()
                            df = pd.read_parquet(BytesIO(blob_data))
                            
                            if config['WEIGHT_CLASS_COLUMN'] in df.columns and config['COUNT_COLUMN'] in df.columns:
                                class_sums = df.groupby(config['WEIGHT_CLASS_COLUMN'])[config['COUNT_COLUMN']].sum()
                                for wc, count in class_sums.items():
                                    counts[str(wc)] += count
                        except Exception:
                            pass
                    
                    if counts:
                        road_has_data = True
                        results[mpo][road_id][year] = dict(counts)
                        all_weight_classes.update(counts.keys())
                    else:
                        results[mpo][road_id][year] = {}
                
                print(f"[{'OK' if road_has_data else 'NO DATA'}]")
        
        weight_classes = sorted(all_weight_classes, 
                               key=lambda x: (x.replace('.', '').isdigit() and int(x.replace('.', '')) or float('inf'), x))
        
        print(f"\n\nWeight classes: {', '.join(weight_classes)}")
        print(f"\nCreating reports...")
        
        create_excel_report(results, config['MPO_LIST'], config['YEARS'], 
                          weight_classes, config['OUTPUT_EXCEL'])
        
        missing_count = generate_missing_data_report(config['OUTPUT_EXCEL'], config['MPO_LIST'], 
                                                     config['YEARS'], weight_classes, config['OUTPUT_MISSING_CSV'])
        
        print("\n" + "="*60)
        print("COMPLETE")
        print("="*60)
        print(f"\nExcel: {config['OUTPUT_EXCEL']}")
        print(f"Missing data: {config['OUTPUT_MISSING_CSV']} ({missing_count} records)")
        print(f"MPO sheets: {len(config['MPO_LIST'])}")
        print("="*60 + "\n")
        
    except KeyboardInterrupt:
        print("\n\nInterrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()