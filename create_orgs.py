"""
Snyk Organization Creator - Phase 1

This script reads Application names from a CSV file and creates a JSON file 
with organizations that need to be created in Snyk.
"""

from typing import Dict, List
import argparse
import json
import sys
from src.logging_utils import setup_logging
from src.csv_utils import read_applications_from_csv
from src.file_utils import sanitize_path, sanitize_input_path, safe_write_json, safe_write_json_to_logs, build_output_path_in_logs, validate_file_exists, log_error_and_exit, validate_non_empty_string


class SnykOrgCreator:
    def __init__(self, group_id: str, debug: bool = False):
        self.group_id = group_id
        self.logger = setup_logging('create_orgs', debug=debug)
    
    def read_applications_from_csv(self, csv_file_path: str) -> List[Dict]:
        """
        Read applications from CSV file for organization creation
        Uses centralized CSV parsing (only repositories) - applications with repos need orgs
        """
        # Sanitize path for safety
        csv_file_path = sanitize_input_path(csv_file_path)
        
        # Use centralized function - only repositories are relevant for org creation
        # (applications without repositories don't need Snyk organizations)
        applications = read_applications_from_csv(csv_file_path, logger=self.logger)
        
        print(f"Found {len(applications)} repository entries from CSV")
        return applications

    def create_orgs_json(self, csv_file_path: str, output_json_path: str, source_org_id: str = None):
        # Sanitize CSV path for safety (output path sanitized in safe_write_json)
        csv_file_path = sanitize_input_path(csv_file_path)
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
        
        # Write to file using secure function - handles all validation and error checking
        if output_json_path.startswith('/') or ':' in output_json_path:
            # Custom path provided - use safe_write_json for direct path writing
            safe_write_json(orgs_json, output_json_path, self.logger)
        else:
            # Filename only - use safe_write_json_to_logs for SNYK_LOG_PATH directory
            filename = os.path.basename(output_json_path)
            safe_write_json_to_logs(orgs_json, filename, self.logger)
        
        print(f"   Organizations to create: {len(orgs_to_create)}")


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
    parser.add_argument('--debug', action='store_true', help='Enable detailed debug logging')
    
    args = parser.parse_args()
    
    # Initialize logging early with debug support
    logger = setup_logging('create_orgs', debug=args.debug)
    logger.info("=== Starting create_orgs.py ===")
    logger.info(f"Command line arguments: {vars(args)}")
    
    # Sanitize input paths (output path sanitized in safe_write_json)
    try:
        args.csv_file = sanitize_input_path(args.csv_file)
    except ValueError as ve:
        log_error_and_exit(f"❌ Error: {ve}", logger)

    # Input validation
    validate_file_exists(args.csv_file, logger)
    validate_non_empty_string(args.group_id, "Group ID", logger)
    
    # Validate source org ID format if provided
    if args.source_org_id:
        validate_non_empty_string(args.source_org_id, "Source org ID", logger)
    
    # Generate automatic filename if not provided
    if not args.output:
        # Use SNYK_LOG_PATH (required environment variable)
        filename = f"group-{args.group_id}-orgs.json"
        output_path = build_output_path_in_logs(filename, logger)
    else:
        # Sanitize output path for safety
        try:
            output_path = sanitize_path(args.output)
        except ValueError as ve:
            log_error_and_exit(f"❌ Error: {ve}", logger)
    
    creator = SnykOrgCreator(args.group_id, debug=args.debug)
    
    message = f"Creating organizations file: {output_path}"
    print(message)
    logger.info(message)
    
    try:
        creator.create_orgs_json(args.csv_file, output_path, args.source_org_id)
        
        success_msg = f"✅ Phase 1 complete! Use this file to create organizations in Snyk: {output_path}"
        print(f"\n{success_msg}")
        logger.info(success_msg)
        logger.info("=== create_orgs.py completed successfully ===")
        
    except Exception as e:
        error_msg = f"❌ Fatal error during organization creation: {e}"
        print(f"\n{error_msg}")
        logger.error(error_msg)
        logger.error("=== create_orgs.py failed ===")
        sys.exit(1)


if __name__ == '__main__':
    main()
