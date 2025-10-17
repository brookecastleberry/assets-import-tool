import csv
from typing import Dict, List

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

def read_applications_from_csv(csv_file_path: str, logger=None) -> List[Dict]:
    """
    Read applications from CSV file with enhanced parsing
    Only processes rows where Type='repository'
    """
    applications = []
    try:
        if PANDAS_AVAILABLE:
            df = pd.read_csv(csv_file_path)
            if 'Application' not in df.columns:
                msg = "Error: 'Application' column not found in CSV"
                if logger: logger.error(msg)
                return []
            if 'Type' not in df.columns:
                msg = "Error: 'Type' column not found in CSV"
                if logger: logger.error(msg)
                return []
            for index, row in df.iterrows():
                # Only process rows where Type='repository'
                asset_type = str(row.get("Type", "")).strip()
                if asset_type.lower() != 'repository':
                    continue
                
                app_name = str(row.get("Application", "")).strip()
                if app_name and app_name.lower() not in ['nan', 'n/a', '', 'none', 'null']:
                    app_names = [name.strip() for name in app_name.split(',') if name.strip() and name.strip().lower() not in ['n/a', 'nan', '', 'none', 'null']]
                    for single_app in app_names:
                        applications.append({
                            'application_name': single_app,
                            'asset_type': str(row.get("Type", "")),
                            'asset_name': str(row.get("Asset", "")),
                            'repository_url': str(row.get("Repository URL", "")),
                            'asset_source': str(row.get("Asset Source", "")),
                            'organizations': str(row.get("Organizations", "")),
                            'row_index': index
                        })
        else:
            with open(csv_file_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                if 'Application' not in reader.fieldnames:
                    msg = "Error: 'Application' column not found in CSV"
                    if logger: logger.error(msg)
                    return []
                if 'Type' not in reader.fieldnames:
                    msg = "Error: 'Type' column not found in CSV"
                    if logger: logger.error(msg)
                    return []
                for index, row in enumerate(reader):
                    # Only process rows where Type='repository'
                    asset_type = row.get("Type", "").strip()
                    if asset_type.lower() != 'repository':
                        continue
                    
                    app_name = row.get("Application", "").strip()
                    if app_name and app_name.lower() not in ['nan', 'n/a', '', 'none', 'null']:
                        app_names = [name.strip() for name in app_name.split(',') if name.strip() and name.strip().lower() not in ['n/a', 'nan', '', 'none', 'null']]
                        for single_app in app_names:
                            applications.append({
                                'application_name': single_app,
                                'asset_type': row.get("Type", ""),
                                'asset_name': row.get("Asset", ""),
                                'repository_url': row.get("Repository URL", ""),
                                'asset_source': row.get("Asset Source", ""),
                                'organizations': row.get("Organizations", ""),
                                'row_index': index
                            })
    except Exception as e:
        if logger: logger.error(f"Error reading CSV file: {e}")
        return []
    if logger: logger.info(f"Found {len(applications)} repository entries from CSV (filtered by Type = Repository)")
    return applications
