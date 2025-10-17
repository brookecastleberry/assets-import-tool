"""
Snyk Organization Creator - Phase 1

This script reads Application names from a CSV file and creates a JSON file 
with organizations that need to be created in Snyk.
"""

import json
import csv
from typing import Dict, List
import argparse
import sys
import os
import logging
from datetime import datetime

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("Warning: pandas not available, using basic CSV parsing")


def setup_logging() -> logging.Logger:
    """
    Setup logging to file using SNYK_LOG_PATH environment variable
    """
    log_path = os.environ.get('SNYK_LOG_PATH')
    if not log_path:
        print("Warning: SNYK_LOG_PATH environment variable not set. Logs will only be displayed on console.")
        # Create a console-only logger
        logger = logging.getLogger('create_orgs')
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            console_handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        return logger
    
    # Ensure the log directory exists
    os.makedirs(log_path, exist_ok=True)
    
    # Create log filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_path, f'create_orgs_{timestamp}.log')
    
    # Setup logger
    logger = logging.getLogger('create_orgs')
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers
    if not logger.handlers:
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    print(f"📝 Logging to: {log_file}")
    return logger


class SnykOrgCreator:
    def __init__(self, group_id: str):
        self.group_id = group_id
        self.logger = setup_logging()
    
    def read_applications_from_csv(self, csv_file_path: str) -> List[Dict]:
        """
        Read applications from CSV file with enhanced parsing
        """
        applications = []
        
        try:
            if PANDAS_AVAILABLE:
                # Try reading normally first
                df = pd.read_csv(csv_file_path)
                
                if 'Application' not in df.columns:
                    print("Error: 'Application' column not found in CSV")
                    print(f"Available columns: {list(df.columns)}")
                    return []
                
                # Process each row
                for index, row in df.iterrows():
                    app_name = str(row.get("Application", "")).strip()
                    if app_name and app_name.lower() not in ['nan', 'n/a', '']:
                        # Handle multiple applications separated by commas
                        app_names = [name.strip() for name in app_name.split(',') 
                                    if name.strip() and name.strip().lower() not in ['n/a', 'nan']]
                        
                        for single_app in app_names:
                            applications.append({
                                'application_name': single_app,
                                'row_index': index
                            })
            else:
                # Basic CSV parsing fallback
                with open(csv_file_path, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    
                    if 'Application' not in reader.fieldnames:
                        error_msg = "Error: 'Application' column not found in CSV"
                        print(error_msg)
                        print(f"Available columns: {reader.fieldnames}")
                        self.logger.error(error_msg)
                        self.logger.error(f"Available columns: {reader.fieldnames}")
                        return []
                    
                    for index, row in enumerate(reader):
                        app_name = row.get("Application", "").strip()
                        if app_name and app_name.lower() not in ['nan', 'n/a', '']:
                            # Handle multiple applications separated by commas
                            app_names = [name.strip() for name in app_name.split(',') 
                                        if name.strip() and name.strip().lower() not in ['n/a', 'nan']]
                            
                            for single_app in app_names:
                                applications.append({
                                    'application_name': single_app,
                                    'row_index': index
                                })
        
        except FileNotFoundError:
            error_msg = f"❌ Error: CSV file not found: {csv_file_path}"
            print(error_msg)
            self.logger.error(error_msg)
            return []
        except PermissionError:
            error_msg = f"❌ Error: Permission denied reading CSV file: {csv_file_path}"
            print(error_msg)
            self.logger.error(error_msg)
            return []
        except UnicodeDecodeError as e:
            error_msg = f"❌ Error: Encoding issue reading CSV file {csv_file_path}: {e}"
            print(error_msg)
            self.logger.error(error_msg)
            return []
        except csv.Error as e:
            error_msg = f"❌ Error: CSV parsing error in {csv_file_path}: {e}"
            print(error_msg)
            self.logger.error(error_msg)
            return []
        except Exception as e:
            error_msg = f"Error reading CSV file: {e}"
            print(error_msg)
            self.logger.error(error_msg)
            return []
        
        print(f"Found {len(applications)} application entries from CSV")
        return applications

    def create_orgs_json(self, csv_file_path: str, output_json_path: str, source_org_id: str = None):
        """
        Create orgs.json file with all unique Application names from CSV
        """
        # Read applications from CSV
        applications = self.read_applications_from_csv(csv_file_path)
        
        if not applications:
            print("❌ No applications found in CSV")
            return
        
        # Find unique application names
        unique_app_names = set()
        for app in applications:
            unique_app_names.add(app['application_name'])
        
        # Validate application names don't exceed 60 characters
        invalid_names = []
        for app_name in unique_app_names:
            if len(app_name) > 60:
                invalid_names.append(app_name)
        
        if invalid_names:
            error_msg = "❌ Error: The following application names exceed 60 characters:"
            print(error_msg)
            self.logger.error(error_msg)
            for invalid_name in sorted(invalid_names):
                invalid_msg = f"   - '{invalid_name}' ({len(invalid_name)} characters)"
                print(invalid_msg)
                self.logger.error(invalid_msg)
            final_msg = f"\nSnyk organization names must be 60 characters or less. Please shorten these application names in your CSV and try again."
            print(final_msg)
            self.logger.error(final_msg)
            sys.exit(1)
        
        print(f"📋 Found {len(unique_app_names)} unique applications to create as organizations:")
        for org_name in sorted(unique_app_names):
            print(f"   - {org_name}")
        
        # Create orgs structure
        orgs_to_create = []
        for org_name in sorted(unique_app_names):
            org_data = {
                "name": org_name,
                "groupId": self.group_id
            }
            
            # Add sourceOrgId if provided
            if source_org_id:
                org_data["sourceOrgId"] = source_org_id
            
            orgs_to_create.append(org_data)
        
        orgs_json = {"orgs": orgs_to_create}
        
        # Write to file with error handling
        try:
            with open(output_json_path, 'w') as f:
                json.dump(orgs_json, f, indent=2)
            
            success_msg = f"📄 Created organizations file: {output_json_path}"
            print(success_msg)
            self.logger.info(success_msg)
            print(f"   Organizations to create: {len(orgs_to_create)}")
            
        except PermissionError:
            error_msg = f"❌ Error: Permission denied writing to {output_json_path}"
            print(error_msg)
            self.logger.error(error_msg)
            sys.exit(1)
        except OSError as e:
            error_msg = f"❌ Error: Failed to write file {output_json_path}: {e}"
            print(error_msg)
            self.logger.error(error_msg)
            sys.exit(1)
        except Exception as e:
            error_msg = f"❌ Error: Unexpected error writing file {output_json_path}: {e}"
            print(error_msg)
            self.logger.error(error_msg)
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Create Snyk organizations from CSV file (Phase 1)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create organizations file
  python create_orgs.py --group-id abc123 --csv-file mydata.csv
  
  # Create organizations with source org for copying settings
  python create_orgs.py --group-id abc123 --csv-file mydata.csv --source-org-id def456
        """
    )
    
    parser.add_argument('--group-id', required=True, help='Snyk Group ID')
    parser.add_argument('--csv-file', required=True, help='CSV file path')
    parser.add_argument('--source-org-id', help='Source organization ID to copy settings from')
    parser.add_argument('--output', help='Output JSON file path (default: group-{GROUP_ID}-orgs.json)')
    
    args = parser.parse_args()
    
    # Initialize logging early
    logger = setup_logging()
    logger.info("=== Starting create_orgs.py ===")
    logger.info(f"Command line arguments: {vars(args)}")
    
    # Input validation
    # Check if CSV file exists
    if not os.path.exists(args.csv_file):
        error_msg = f"❌ Error: CSV file not found: {args.csv_file}"
        print(error_msg)
        logger.error(error_msg)
        sys.exit(1)
    
    # Validate group ID format (basic UUID check)
    if not args.group_id or len(args.group_id.strip()) == 0:
        error_msg = "❌ Error: Group ID cannot be empty"
        print(error_msg)
        logger.error(error_msg)
        sys.exit(1)
    
    # Validate source org ID format if provided
    if args.source_org_id and len(args.source_org_id.strip()) == 0:
        error_msg = "❌ Error: Source org ID cannot be empty if provided"
        print(error_msg)
        logger.error(error_msg)
        sys.exit(1)
    
    # Generate automatic filename if not provided
    if not args.output:
        output_path = f"group-{args.group_id}-orgs.json"
    else:
        output_path = args.output
    
    creator = SnykOrgCreator(args.group_id)
    
    message = f"Creating organizations file: {output_path}"
    print(message)
    logger.info(message)
    
    try:
        creator.create_orgs_json(args.csv_file, output_path, args.source_org_id)
        
        success_msg = f"✅ Phase 1 complete! Use this file to create organizations in Snyk: {output_path}"
        print(f"\n{success_msg}")
        logger.info(success_msg)
        
        next_steps = f"📋 Next steps: 1. Use Snyk API Import Tool to create organizations from {output_path} 2. Then run: python create_targets.py --group-id {args.group_id} --csv-file {args.csv_file} --integration-type YOUR_INTEGRATION_TYPE"
        print(f"\n📋 Next steps:")
        print(f"   1. Use Snyk API Import Tool to create organizations from {output_path}")
        print(f"   2. Then run: python create_targets.py --group-id {args.group_id} --csv-file {args.csv_file} --integration-type YOUR_INTEGRATION_TYPE")
        logger.info(next_steps)
        logger.info("=== create_orgs.py completed successfully ===")
        
    except Exception as e:
        error_msg = f"❌ Fatal error during organization creation: {e}"
        print(f"\n{error_msg}")
        logger.error(error_msg)
        logger.error("=== create_orgs.py failed ===")
        sys.exit(1)


if __name__ == '__main__':
    main()
