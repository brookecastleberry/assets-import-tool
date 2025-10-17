# Assets Import Tool for Snyk

A comprehensive tool for importing repositories from various SCM platforms into Snyk organizations with proper application boundary enforcement.

![Snyk OSS Example](https://raw.githubusercontent.com/snyk-labs/oss-images/main/oss-example.jpg)

## 🎯 Overview

This tool provides a complete workflow for importing repositories into Snyk while maintaining organizational boundaries based on your application structure. It integrates with `snyk-api-import` to provide enterprise-scale import capabilities with enhanced authentication and filtering.

## 🏗️ Architecture

The import process follows a 4-step workflow:

1. **Generate Organization Data**: Create Snyk organization structure from your CSV (`create_orgs.py`)
2. **Create Organizations in Snyk**: Use `snyk-api-import` to create the organizations in Snyk
3. **Generate Import Targets**: Create repository import targets with automatic SCM integration and application boundary enforcement (`create_targets.py`)
4. **Import Repositories**: Use `snyk-api-import` to perform the actual repository imports into Snyk

## 📋 Prerequisites

### Required Files
- `assets.csv` - Repository inventory with Application column mapping

### Environment Variables

**Required:**

*Standard Authentication:*
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

## 📄 Generated Files

This tool creates the following files that are used by `snyk-api-import`:

- `group-{GROUP_ID}-orgs.json` - Snyk organization structure (from `create_orgs.py`)
- `import-targets.json` - Repository import targets (from `create_targets_fixed.py`)

*Note: Both output filenames can be customized using the `--output` parameter.*

## 📝 Logging

Both scripts automatically generate detailed log files in `SNYK_LOG_PATH`:

- **create_orgs.py** → `create_orgs_YYYYMMDD_HHMMSS.log`
- **create_targets_fixed.py** → `create_targets_YYYYMMDD_HHMMSS.log`


The logs capture:
- Command line arguments and execution start/end
- CSV parsing results and organization loading
- HTTP request failures and rate limiting events
- Error details with full stack traces
- Performance metrics and auto-tuning decisions

## ⚠️ Error Handling

Both scripts include robust error handling:
- All errors are logged with full stack traces and context
- HTTP/API failures are retried with exponential backoff
- CSV parsing errors and missing/invalid data are reported in the logs
- Rate limit events and timeouts are captured and logged
- The scripts exit with a non-zero status code on fatal errors

Check the log files in your `SNYK_LOG_PATH` for detailed error diagnostics and troubleshooting information.


## 🚀 Quick Start

### Step 1: Generate Organization Data

```bash
# Generate Snyk organization structure from your CSV data
python create_orgs.py --group-id YOUR_GROUP_ID --source-org-id YOUR_SOURCE_ORG_ID --csv-file assets.csv
```


**Output**: `group-YOUR_GROUP_ID-orgs.json`

> **Note:** Organization data will only be generated for unique Application org names found in the CSV file. Duplicate Application names will be ignored for org creation.

### Step 2: Create Organizations in Snyk

```bash
# Use snyk-api-import to create the organizations in Snyk
snyk-api-import orgs:create --file=group-YOUR_GROUP_ID-orgs.json
```

### Step 3: Generate Import Targets

```bash
# Generate import targets with automatic SCM integration and boundary enforcement
python create_targets_fixed.py --group-id YOUR_GROUP_ID --csv-file assets.csv --orgs-json snyk-created-orgs.json --source github
```

**Output**: `import-targets.json`

### Step 4: Import Repositories

```bash
# Use snyk-api-import to perform the actual repository imports
snyk-api-import import --file=import-targets.json

# For debugging issues, use the debug version:
DEBUG=*snyk* snyk-api-import import --file=import-targets.json
```

### **Custom Performance Tuning (Optional)**
```bash
# Override auto-tuning if needed
python create_targets_fixed.py \
  --group-id YOUR_GROUP_ID \
  --csv-file your-data.csv \
  --orgs-json group-YOUR_GROUP_ID-orgs.json \
  --source github \
  --max-workers 25 \
  --rate-limit 30
```

## � Command Line Reference

### create_orgs.py - Organization Generator

**Required Flags:**
- `--group-id` - Snyk Group ID where organizations will be created
- `--csv-file` - Path to CSV file containing Application data

**Optional Flags:**
- `--source-org-id` - Source organization ID to copy settings from (recommended for consistent configuration)
- `--output` - Custom output file path (default: `group-{GROUP_ID}-orgs.json`)

**Example:**
```bash
python create_orgs.py --group-id abc123 --source-org-id def456 --csv-file assets.csv --output my-orgs.json
```

### create_targets_fixed.py - Import Targets Generator

**Required Flags:**
- `--group-id` - Snyk Group ID where repositories will be imported
- `--csv-file` - Path to CSV file containing repository data
- `--orgs-json` - Path to snyk-created-orgs.json 
- `--source` - Integration type (one at a time): `github`, `github-cloud-app`, `github-enterprise`, `gitlab`, `azure-repos`

**Optional Flags:**

*Output & Filtering:*
- `--output` - Custom output file path (default: `import-targets.json`)
- `--empty-org-only` - Only process repositories where Organizations column is "N/A" (repositories not yet imported to Snyk)
- `--limit` - Maximum number of repository targets to process (useful for batching)

*Repository Configuration Overrides (applies to all repositories):*
- `--branch` - Override branch for all repositories (default: auto-detect)
- `--files` - Override files to scan for all repositories - comma-separated list (default: omitted for full scan)
- `--exclusion-globs` - Override exclusion patterns for all repositories (default: `"fixtures, tests, __tests__, node_modules"`)

*Performance Tuning:*
- `--max-workers` - Maximum concurrent workers (default: auto-tuned based on repository count)
- `--rate-limit` - Maximum requests per minute (default: auto-tuned based on source type)

**Example:**
```bash
python create_targets_fixed.py --group-id abc123 --csv-file assets.csv --orgs-json group-abc123-orgs.json --source github --branch main --files "package.json" --exclusion-globs "test,spec" --max-workers 20 --rate-limit 100
```


## ⚡ Performance & Rate Limiting

### SCM API Rate Limits

The tool automatically respects SCM platform rate limits:

| Platform | API Rate Limit | Tool Default | Notes |
|----------|----------------|--------------|-------|
| **GitHub** | 5,000 req/hour (83 req/min) | 80 req/min | Uses GitHub REST API v3 |
| **GitLab** | 300 req/min | 250 req/min | Uses GitLab REST API v4 |
| **Azure DevOps** | 200 req/min | 150 req/min | Uses Azure DevOps REST API 7.0 |

### Auto-Tuning

**Concurrent Workers:** Automatically scales from 10 workers (≤100 repos) to 50 workers (5,000+ repos)

**Rate Limiting:** Tool defaults are conservative to prevent API throttling

```

## 📊 Performance Comparison

| Repository Count | Traditional (Sequential) | Enterprise (Auto-Tuned) | Time Saved |
|------------------|-------------------------|-------------------------|------------|
| 100             | 10-15 minutes           | 2-3 minutes             | 70%        |
| 1,000           | 100-150 minutes         | 15-20 minutes           | 85%        |
| 5,000           | 8-12 hours              | 60-90 minutes           | 90%        |
| 10,000          | 16-24 hours             | 2-3 hours               | 87%        |

*Performance with automatic worker scaling and source-aware rate limiting*

**Auto-Tuning Examples:**
- **50 repos**: 10 workers, 80 req/min (GitHub)
- **1,000 repos**: 20 workers, 250 req/min (GitLab)  
- **5,000 repos**: 40 workers, 150 req/min (Azure DevOps)

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

| Integration Type | Matches Asset Source Keywords |
|------------------|-------------------------------|
| `github`         | "github"                     |
| `gitlab`         | "gitlab"                     |
| `azure-repos`    | "azure", "devops"           |

Example CSV:
```csv
Application,Type,Asset,Repository URL,Asset Source
MyApp,Repository,Backend Service,https://github.com/company/myapp,GitHub Enterprise
DataPipe,Repository,Data Pipeline,https://gitlab.com/company/data,GitLab SaaS
WebApp,Repository,Frontend,https://dev.azure.com/company/project/_git/webapp,Azure DevOps
```

## 🤖 Auto-Detection Features

🤖 **Branch Detection**: Automatically detects default branch via repository APIs
🔍 **GitLab Project ID**: Auto-detects project IDs for GitLab repositories  
⚡ **Integration Matching**: Smart filtering based on Asset Source keywords


## 🔗 Integration Types

Supported integration types:
- `github` - GitHub
- `github-cloud-app` - GitHub Cloud App
- `github-enterprise` - GitHub Enterprise
- `gitlab` - GitLab  
- `azure-repos` - Azure DevOps

**Note**: Bitbucket integrations are not currently supported.



