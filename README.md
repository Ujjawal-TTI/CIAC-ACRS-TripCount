# CIAC-ACRS-TripCount

Installation
pip install pandas azure-storage-blob xlsxwriter sqlalchemy psycopg2-binary

Pipeline Overview
Script 1: Extract trip data from Azure → Generate Excel report + Missing Data CSV
Script 2: Compare Missing Data CSV with PostgreSQL database → Identify coverage gaps

Script 1: MPO Road Trip Analysis (trip_count_from_azure.py)
Purpose: Analyze vehicle trip counts by weight class across MPOs, Road IDs, and years.

Configuration
Edit CONFIG section in script: Insert SAS token
Outputs:
MPO_Road_Trip_Analysis.xlsx - Excel workbook with:
Summary sheet (all MPOs aggregated)
MPO_Missing_Data_List.csv - Roads with zero data (Year, MPO, Road ID)


*********
Script 2: Missing Data Comparison
Purpose: Compare missing data records against PostgreSQL database to identify coverage.

Configuration
Edit CONFIG section in script: add path to the above generate 'MPO_Missing_Data_List.csv' file.

Prompts for: Database Host, Database Name, Username, Password (hidden input), Port (default: 5432)

Outputs:
Not_In_Lookup.csv - Missing data records NOT found in database
In_Both_Files.csv - Missing data records found in database
Console summary with coverage percentage

Notes
Script 1 runtime: Varies based on data volume (typically 10-60 minutes)
Script 2 password: Input is hidden for security (nothing displays while typing)
Database types: PostgreSQL supported; easily adaptable for SQL Server/MySQL
Years: Configurable in both scripts
