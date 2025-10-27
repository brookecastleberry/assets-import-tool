# Assets Import Tool for Snyk

A comprehensive tool for importing repositories from various SCM platforms into Snyk organizations with proper application boundary enforcement.

![Snyk OSS Example](https://raw.githubusercontent.com/snyk-labs/oss-images/main/oss-example.jpg)

## 🎯 Overview

This tool provides a complete workflow for importing repositories into Snyk while maintaining organizational boundaries based on your application structure. It integrates with [`snyk-api-import`](https://github.com/snyk/snyk-api-import) to provide enterprise-scale import capabilities with enhanced authentication and filtering.

## 🏗️ Architecture

The import process follows a 4-step workflow:

1. **Generate Organization Data**: Create Snyk organization structure from your CSV (`create_orgs.py`)
2. **Create Organizations in Snyk**: Use `snyk-api-import` to create the organizations in Snyk
3. **Generate Import Targets**: Create repository import targets with automatic SCM integration and application boundary enforcement (`create_targets.py`)
4. **Import Repositories**: Use `snyk-api-import` to perform the actual repository imports into Snyk

## 📋 Prerequisites

### Required Files
- `all_assets.csv` - Repository inventory with Application column mapping

**To generate the `all_assets.csv` file:**
1. Go to your Snyk Group dashboard
2. Navigate to **Inventory** tab
3. Select **All Assets**
4. Click **Export** to download the CSV file

### Environment Variables

**Required:**
```bash
export GITHUB_TOKEN="your_github_personal_access_token"
export GITLAB_TOKEN="your_gitlab_personal_access_token" 
export AZURE_DEVOPS_TOKEN="your_azure_devops_personal_access_token"
export SNYK_TOKEN="your_snyk_token"
export SNYK_LOG_PATH="/path/to/logs"
# Example: mkdir -p "$HOME/snyk-logs" && export SNYK_LOG_PATH="$HOME/snyk-logs"
```

### Dependencies
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install snyk-api-import
npm install -g snyk-api-import
```

### Corporate Networks & SSL (Optional)
**Only needed if you get SSL errors**: If you're behind a corporate network with SSL inspection, set:
```bash
export REQUESTS_CA_BUNDLE=/path/to/your/corporate-ca-bundle.pem
```

## 📄 Generated Files

This tool creates the following files that are used by `snyk-api-import`:

- `group-{GROUP_ID}-orgs.json` - Snyk organization structure (from `create_orgs.py`)
- `import-targets.json` - Repository import targets (from `create_targets.py`)

**Output Location:**
- Files are created in the `SNYK_LOG_PATH` directory (environment variable required)
- Both output filenames and paths can be customized using the `--output` parameter

## 🚀 Quick Start

### Step 1: Generate Organization Data

```bash
# Generate Snyk organization structure from your CSV data
python create_orgs.py --group-id YOUR_GROUP_ID --source-org-id YOUR_SOURCE_ORG_ID --csv-file /path/to/all_assets.csv
```


**Output**: `$SNYK_LOG_PATH/group-YOUR_GROUP_ID-orgs.json`

> **Note:** Organization data will only be generated for unique Application org names found in the CSV file. Duplicate Application names will be ignored for org creation.

### Step 2: Create Organizations in Snyk

```bash
# Use snyk-api-import to create the organizations in Snyk
snyk-api-import orgs:create --file=$SNYK_LOG_PATH/group-YOUR_GROUP_ID-orgs.json
```

**Output**: `$SNYK_LOG_PATH/snyk-created-orgs.json` (created by snyk-api-import)

### Step 3: Generate Import Targets

```bash
# Generate import targets with automatic SCM integration and boundary enforcement
python create_targets.py --group-id YOUR_GROUP_ID --csv-file /path/to/all_assets.csv --orgs-json $SNYK_LOG_PATH/snyk-created-orgs.json --source github
```

**Output**: `$SNYK_LOG_PATH/import-targets.json`

### Step 4: Import Repositories

```bash
# Use snyk-api-import to perform the actual repository imports
snyk-api-import import --file=$SNYK_LOG_PATH/import-targets.json

# For debugging issues, use the debug version:
DEBUG=*snyk* snyk-api-import import --file=$SNYK_LOG_PATH/import-targets.json
```

### **Custom Performance Tuning (Optional)**
```bash
# Override auto-tuning if needed
python create_targets.py \
  --group-id YOUR_GROUP_ID \
  --csv-file your-data.csv \
  --orgs-json $SNYK_LOG_PATH/snyk-created-orgs.json \
  --source github \
  --max-workers 25 \
  --rate-limit 30
```

## � Command Line Reference

### create_orgs.py - Organization Generator

**Required Flags:**
- `--group-id` - Snyk Group ID where organizations will be created
- `--csv-file` - Full path to CSV file containing Application data (e.g., `/path/to/all_assets.csv`)

**Optional Flags:**
- `--source-org-id` - Source organization ID to copy settings from (recommended for consistent configuration)
- `--output` - Custom output file path (default: `$SNYK_LOG_PATH/group-{GROUP_ID}-orgs.json`)
- `--debug` - Enable detailed debug logging

**Example:**
```bash
python create_orgs.py --group-id abc123 --source-org-id def456 --csv-file /path/to/all_assets.csv --output my-orgs.json --debug
```

### create_targets.py - Import Targets Generator

**Required Flags:**
- `--group-id` - Snyk Group ID where repositories will be imported
- `--csv-file` - Full path to CSV file containing repository data (e.g., `/path/to/all_assets.csv`)
- `--orgs-json` - Path to snyk-created-orgs.json 
- `--source` - Integration type (one at a time): `github`, `github-cloud-app`, `github-enterprise`, `gitlab`, `azure-repos`

**Optional Flags:**

*Output & Filtering:*
- `--output` - Custom output file path (default: `$SNYK_LOG_PATH/import-targets.json`)
- `--empty-org-only` - Only process repositories where Organizations column is "N/A" (repositories not yet imported to Snyk)
- `--limit` - Maximum number of repository targets to process (useful for batching)
- `--rows` - Specify CSV row numbers to process (e.g., `--rows 2,5-8,10` for rows 2, 5-8, and 10)

*Filtering Order of Precedence:*
When multiple filtering flags are used together, they are applied in this specific order:
1. **`--rows`** (highest precedence) - First, select only the specified CSV rows
2. **`--empty-org-only`** - Then, filter out repositories that already have Snyk organizations
3. **`--source`** - Then, filter by integration type (GitHub, GitLab, etc.)
4. **`--limit`** (lowest precedence) - Finally, limit the number of results

*Example:* `--rows 1-100 --empty-org-only --source github --limit 5`
- Processes CSV rows 1-100 (100 repositories)
- Filters to only empty orgs (maybe 60 repositories remain)  
- Filters to only GitHub repositories (maybe 30 repositories remain)
- Limits output to first 5 repositories (final result: 5 repositories)

*Repository Configuration Overrides (applies to all repositories):*
- `--branch` - Override branch for all repositories (default: auto-detect)
- `--files` - Override files to scan for all repositories - comma-separated list (default: omitted for full scan)
- `--exclusion-globs` - Override exclusion patterns for all repositories (default: `"fixtures, tests, __tests__, node_modules"`)

*Performance Tuning:*
- `--max-workers` - Maximum concurrent workers (default: auto-tuned based on repository count)
- `--rate-limit` - Maximum requests per minute (default: auto-tuned based on source type)

*Debugging & Troubleshooting:*
- `--debug` - Enable detailed debug logging (API requests, responses, timing, error traces)

**Example:**
```bash
python create_targets.py --group-id abc123 --csv-file /path/to/all_assets.csv --orgs-json $SNYK_LOG_PATH/snyk-created-orgs.json --source github --branch main --files "package.json" --exclusion-globs "test,spec" --max-workers 20 --rate-limit 100 --debug
```

## 🔍 Debug Logging

Add `--debug` to enable detailed logging for troubleshooting (API requests, timing, error traces). Without it, tools run silently with clean output.

## ⚡ Performance & Rate Limiting

### SCM API Rate Limits

The tool automatically respects SCM platform rate limits:

| Platform | API Rate Limit | Tool Default | Notes |
|----------|----------------|--------------|-------|
| **GitHub** | 5,000 req/hour (83 req/min) | 80 req/min | Uses GitHub REST API v3 |
| **GitLab** | 300 req/min | 250 req/min | Uses GitLab REST API v4 |
| **Azure DevOps** | 200 req/min | 150 req/min | Uses Azure DevOps REST API 7.0 |

### Auto-Tuning

**Concurrent Workers:** Automatically scales based on repository count (10-50 workers)

**Rate Limiting:** Automatically adjusted by SCM type to prevent API throttling


## 📋 CSV File Format

Your CSV should include these columns:

**Required:**
- `Application` - The application/organization name  
- `Type` - Must be "Repository" for filtering
- `Repository URL` - Full URL to the repository
- `Asset Source` - Source system (GitHub, GitLab, etc.)


**Note:** The tool handles CSV files with title rows automatically, filters by `Type="Repository"`, and skips any repository row where the Application cell is empty.

## 🔍 Asset Source Filtering

The script uses the `Asset Source` column to filter repositories by integration type:

| Integration Type    | Matches Asset Source Keywords |
|---------------------|-------------------------------|
| `github`            | "github"                     |
| `github-cloud-app`  | "github"                     |
| `github-enterprise` | "github"                     |
| `gitlab`            | "gitlab"                     |
| `azure-repos`       | "azure", "devops"           |


## 🤖 Auto-Detection Features

🤖 **Branch Detection**: Automatically detects default branch via repository APIs

🔍 **GitLab Project ID**: Auto-detects project IDs for GitLab repositories  

⚡ **Integration Matching**: Smart filtering based on Repository URL OR Asset Source (if either matches the SCM type, it's included)


## 🔗 Integration Types

Supported integration types:
- `github` - GitHub
- `github-cloud-app` - GitHub Cloud App
- `github-enterprise` - GitHub Enterprise
- `gitlab` - GitLab  
- `azure-repos` - Azure DevOps

**Note**: Bitbucket integrations are not currently supported.



