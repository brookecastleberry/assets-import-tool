# Snyk Assets Import Tool

This tool helps you import repositories into Snyk using a simple two-phase approach:
1. **Phase 1**: Creating organizations that don't exist yet
2. **Phase 2**: Creating import targets for repositories

## Files

- **`create_orgs.py`** - Phase 1: Creates organizations from CSV data
- **`create_targets.py`** - Phase 2: Creates import targets from CSV data

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set your Snyk token:
```bash
export SNYK_TOKEN='your-snyk-token-here'
```

## Usage

### Two-Phase Workflow (Recommended)

#### Phase 1: Create Organizations

```bash
python create_orgs.py --group-id YOUR_GROUP_ID --csv-file your-data.csv
```

This creates a `group-YOUR_GROUP_ID-orgs.json` file with organizations that need to be created.

**Use the Snyk API Import Tool to create these organizations first!**

#### Phase 2: Create Import Targets

```bash
4. **Phase 2 - Create targets  
python create_targets.py --group-id 3de0eeb1-20e3-4afd-8a6a-97d57326588d --csv-file mydata.csv --integration-type github
```

This creates an `import-targets.json` file ready for the Snyk API Import Tool.

### Options

#### Create Organizations (Phase 1)
```bash
# Basic usage
python create_orgs.py --group-id abc123 --csv-file mydata.csv

# With source org (copies settings from existing org)
python create_orgs.py --group-id abc123 --csv-file mydata.csv --source-org-id def456

# Custom output file
python create_orgs.py --group-id abc123 --csv-file mydata.csv --output my-orgs.json
```

#### Create Targets (Phase 2)
```bash
# Single integration type
python create_targets.py --group-id abc123 --csv-file mydata.csv --integration-type github

# Multiple integration types
python create_targets.py --group-id abc123 --csv-file mydata.csv --integration-type github,azure-repos

# Custom output file
python create_targets.py --group-id abc123 --csv-file mydata.csv --integration-type gitlab --output my-targets.json
```

## CSV File Format

Your CSV should include these columns:

**Required:**
- `Application` - The application/organization name
- `Repository URL` - Full URL to the repository

**Optional:**
- `Type` - Asset type
- `Asset` - Asset name  
- `Asset Source` - Source system
- `Gitlab Project ID` - For GitLab repositories
- `Branch` - Specific branch to import
- `exclusionGlobs` - Files/folders to exclude
- `Files` - Specific files to include

**Note:** The tool handles CSV files with title rows automatically.

## Workflow Types

The tool automatically detects the workflow type:

- **GitLab Workflow**: If `Gitlab Project ID` column has values
- **General Workflow**: For GitHub, Azure DevOps, Bitbucket

## Integration Types

Supported integration types:
- `github` - GitHub
- `gitlab` - GitLab  
- `azure-repos` - Azure DevOps
- `bitbucket-cloud` - Bitbucket Cloud
- `bitbucket-server` - Bitbucket Server
- `github-enterprise` - GitHub Enterprise

## Example Workflow

1. **Prepare your CSV** with Application names and Repository URLs
2. **Phase 1**: `python create_orgs.py --group-id abc123 --csv-file data.csv`
3. **Create organizations** in Snyk using the generated JSON file
4. **Phase 2**: `python create_targets.py --group-id abc123 --csv-file data.csv`  
5. **Import repositories** in Snyk using the generated targets file
