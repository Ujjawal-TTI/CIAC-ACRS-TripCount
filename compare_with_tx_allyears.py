import pandas as pd
import sys
from sqlalchemy import create_engine, text
from getpass import getpass

# configuration
CONFIG = {
    # Primary file from previous script
    'PRIMARY_FILE': 'MPO_Missing_Data_List.csv',
    
    # Database settings
    'DATABASE': {
        'type': 'postgresql',
        'default_port': 5432,
        
        #query 
        'query': """
            SELECT year, top100id, mpo
            FROM data_hub.tx100_allyears;
        """
    },
    
    'COLUMN_MAPPING': {
        'primary_year': 'Year',
        'primary_road_id': 'Road ID',
        'lookup_year': 'year',
        'lookup_road_id': 'top100id'
    },
    
    # output files
    'OUTPUT': {
        'not_in_lookup': 'Not_In_Lookup.csv',
        'in_both': 'In_Both_Files.csv'
    }
}

def get_database_credentials():
    print("\n" + "="*60)
    print("DATABASE CONNECTION")
    host = input("Database Host: ")
    database = input("Database Name: ")
    username = input("Username: ")
    password = getpass("Password (hidden): ")
    port = input(f"Port (default {CONFIG['DATABASE']['default_port']}): ").strip()
    
    if not port:
        port = CONFIG['DATABASE']['default_port']
    
    return {
        'host': host,
        'database': database,
        'username': username,
        'password': password,
        'port': port
    }

def connect_to_database(credentials):
    connection_string = (
        f"postgresql+psycopg2://{credentials['username']}:{credentials['password']}"
        f"@{credentials['host']}:{credentials['port']}/{credentials['database']}"
    )
    
    print("\nConnecting to database...")
    try:
        engine = create_engine(connection_string)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Connected successfully")
        return engine
    except Exception as e:
        print(f"ERROR: Database connection failed")
        print(f"Details: {str(e)}")
        sys.exit(1)

def fetch_lookup_data(engine, query):
    """Execute query and return DataFrame"""
    print("\nExecuting query...")
    try:
        df = pd.read_sql(query, engine)
        print(f"Retrieved {len(df)} records")
        return df
    except Exception as e:
        print(f"ERROR: Query execution failed")
        print(f"Details: {str(e)}")
        sys.exit(1)

def compare_datasets(df_primary, df_lookup, col_map):
    """Compare primary and lookup datasets"""
    primary_year = col_map['primary_year']
    primary_road = col_map['primary_road_id']
    lookup_year = col_map['lookup_year']
    lookup_road = col_map['lookup_road_id']
    
    for col, df, name in [
        (primary_year, df_primary, 'primary'),
        (primary_road, df_primary, 'primary'),
        (lookup_year, df_lookup, 'lookup'),
        (lookup_road, df_lookup, 'lookup')
    ]:
        if col not in df.columns:
            print(f"ERROR: Column '{col}' not found in {name} data")
            print(f"Available: {list(df.columns)}")
            sys.exit(1)
    
    # Create comparison keys
    df_primary['compare_key'] = (
        df_primary[primary_year].astype(str) + '_' + 
        df_primary[primary_road].astype(str)
    )
    
    df_lookup['compare_key'] = (
        df_lookup[lookup_year].astype(str) + '_' + 
        df_lookup[lookup_road].astype(str)
    )
    
    # Compare
    primary_keys = set(df_primary['compare_key'])
    lookup_keys = set(df_lookup['compare_key'])
    
    not_in_lookup_keys = primary_keys - lookup_keys
    in_both_keys = primary_keys & lookup_keys
    
    df_not_in_lookup = df_primary[df_primary['compare_key'].isin(not_in_lookup_keys)].drop(columns=['compare_key'])
    df_in_both = df_primary[df_primary['compare_key'].isin(in_both_keys)].drop(columns=['compare_key'])
    
    return df_not_in_lookup, df_in_both

def main():
    print("="*60)
    print("MPO MISSING DATA COMPARISON")
    print("="*60)
    
    # Load primary file
    print(f"\nLoading primary file: {CONFIG['PRIMARY_FILE']}")
    try:
        df_primary = pd.read_csv(CONFIG['PRIMARY_FILE'])
        print(f"Primary records: {len(df_primary)}")
    except FileNotFoundError:
        print(f"ERROR: File not found: {CONFIG['PRIMARY_FILE']}")
        sys.exit(1)
    
    credentials = get_database_credentials()
    engine = connect_to_database(credentials)
    df_lookup = fetch_lookup_data(engine, CONFIG['DATABASE']['query'])
    engine.dispose()

    print("\nComparing datasets...")
    df_not_in_lookup, df_in_both = compare_datasets(
        df_primary, 
        df_lookup, 
        CONFIG['COLUMN_MAPPING']
    )
    
    df_not_in_lookup.to_csv(CONFIG['OUTPUT']['not_in_lookup'], index=False)
    df_in_both.to_csv(CONFIG['OUTPUT']['in_both'], index=False)
    
    print("RESULTS")
    print("="*60)
    print(f"Not in lookup: {len(df_not_in_lookup)} -> {CONFIG['OUTPUT']['not_in_lookup']}")
    print(f"In both files: {len(df_in_both)} -> {CONFIG['OUTPUT']['in_both']}")
    
    if len(df_primary) > 0:
        coverage = len(df_in_both) / len(df_primary) * 100
        print(f"Coverage: {coverage:.1f}%")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)