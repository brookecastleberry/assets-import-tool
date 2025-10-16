# Assets Import Tool for Snyk

A comprehensive toolkit for importing repositories from various SCM platforms into Snyk organizations with proper application boundary enforcement.

## 🎯 Overview

This tool provides a complete workflow for importing repositories into Snyk while maintaining organizational boundaries based on your application structure. It integrates with `snyk-api-import` to provide enterprise-scale import capabilities with enhanced authentication and filtering.

## 🏗️ Architecture

The import process follows a 4-step workflow:

1. **Transform**: Prepare Snyk org data for snyk-api-import compatibility
2. **Generate**: Use snyk-api-import to create import targets
3. **Filter**: Enforce application boundaries to prevent cross-org contamination
4. **Import**: Execute the filtered import to Snyk

## 📋 Prerequisites

### Required Files
- `assets.csv` - Repository inventory with Application column mapping
- `snyk-created-orgs.json` - Your Snyk organization structure

### Environment Variables (for private repos and API discovery)
```bash
export GITHUB_TOKEN="your_github_token"
export GITLAB_TOKEN="your_gitlab_token" 
export AZURE_DEVOPS_TOKEN="your_azure_token"
export BITBUCKET_TOKEN="your_bitbucket_token"
export SNYK_TOKEN="your_snyk_token"
```

### Dependencies
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install snyk-api-import
npm install -g snyk-api-import
```

## 🚀 Quick Start

### Step 1: Transform Organizations

Choose your discovery method:

**CSV Extraction Mode** (uses existing assets.csv data):
```bash
python transform_orgs_for_import.py --source github
```

**API Discovery Mode** (discovers all accessible organizations):
```bash
python transform_orgs_for_import.py --source github --api-discovery
```

**Output**: `snyk-created-orgs-transformed-github-api.json`

### Step 2: Generate Import Targets

```bash
snyk-api-import import --file=snyk-created-orgs-transformed-github-api.json
```

**Output**: `github-import-targets.json`

### Step 3: Filter by Application Boundaries

```bash
python filter_import_targets.py \
  --targets github-import-targets.json \
  --csv assets.csv \
  --output filtered-github-targets.json
```

### Step 4: Import to Snyk

```bash
snyk-api-import import --file=filtered-github-targets.json
```

**Use the Snyk API Import Tool to create these organizations first!**

#### Phase 2: Create Import Targets

```bash
# Basic usage (Enterprise optimized with auto-detection)
python create_targets.py --group-id YOUR_GROUP_ID --csv-file your-data.csv --orgs-json snyk-created-orgs.json --source github
```

This creates an `import-targets.json` file ready for the Snyk API Import Tool.

## 🚀 Enterprise Scale Usage

### **Auto-Tuned Performance (Default)**
```bash
# Works for any scale - automatically optimized!
python create_targets.py --group-id YOUR_GROUP_ID --csv-file your-data.csv --orgs-json snyk-created-orgs.json --source github

# 10,000+ repositories? Still just one command:
python create_targets.py --group-id YOUR_GROUP_ID --csv-file large-dataset.csv --orgs-json snyk-created-orgs.json --source github
```

### **Custom Performance Tuning (Optional)**
```bash
# Override auto-tuning if needed
python create_targets.py \
  --group-id YOUR_GROUP_ID \
  --csv-file your-data.csv \
  --orgs-json snyk-created-orgs.json \
  --source github \
  --max-workers 25 \
  --rate-limit 30
```

### **Quick Test with Sample Data**
```bash
# Generate test data
python create_test_data.py --repos 100

# Test enterprise features
python create_targets.py \
  --group-id test-group \
  --csv-file test-repos.csv \
  --orgs-json test-orgs.json \
  --source github \
  --max-workers 5
```

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

#### Create Targets (Phase 2) - Enterprise Enhanced ⭐
```bash
# Required parameters
python create_targets.py --group-id abc123 --csv-file mydata.csv --orgs-json snyk-created-orgs.json --source github

# Enterprise performance tuning
python create_targets.py --group-id abc123 --csv-file mydata.csv --orgs-json snyk-created-orgs.json --source github --max-workers 20 --rate-limit 800

# Global overrides for all repositories  
python create_targets.py --group-id abc123 --csv-file mydata.csv --orgs-json snyk-created-orgs.json --source github --branch main --files "package.json" --exclusion-globs "test,spec"

# Custom output file
python create_targets.py --group-id abc123 --csv-file mydata.csv --orgs-json snyk-created-orgs.json --source gitlab --output my-targets.json
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
- **50 repos**: 5 workers, 60 req/min (GitHub)
- **1,000 repos**: 12 workers, 48 req/min (GitHub)  
- **5,000 repos**: 15 workers, 42 req/min (GitHub)
- **GitLab**: 200 req/min base, Bitbucket: 12 req/min base

## CSV File Format

Your CSV should include these columns:

**Required:**
- `Application` - The application/organization name  
- `Type` - Must be "Repository" for filtering
- `Repository URL` - Full URL to the repository
- `Asset Source` - Source system (GitHub, GitLab, etc.)

**Optional:**
- `Asset` - Asset description

**Removed Columns** (now auto-detected or overridden via command line):
- ~~`Gitlab Project ID`~~ - Auto-detected via GitLab API
- ~~`Branch`~~ - Auto-detected or use `--branch` override
- ~~`exclusionGlobs`~~ - Use `--exclusion-globs` override  
- ~~`Files`~~ - Use `--files` override

**Note:** The tool handles CSV files with title rows automatically and filters by `Type="Repository"`.

## Asset Source Filtering

The script uses the `Asset Source` column to filter repositories by integration type:

| Integration Type | Matches Asset Source Keywords |
|------------------|-------------------------------|
| `github`         | "github"                     |
| `gitlab`         | "gitlab"                     |
| `azure-repos`    | "azure", "devops"           |
| `bitbucket-cloud`| "bitbucket"                 |

Example CSV:
```csv
Application,Type,Asset,Repository URL,Asset Source
MyApp,Repository,Backend Service,https://github.com/company/myapp,GitHub Enterprise
DataPipe,Repository,Data Pipeline,https://gitlab.com/company/data,GitLab SaaS
WebApp,Repository,Frontend,https://bitbucket.org/company/web,Bitbucket Cloud
```

## Auto-Detection Features

🤖 **Branch Detection**: Automatically detects default branch via repository APIs
🔍 **GitLab Project ID**: Auto-detects project IDs for GitLab repositories  
⚡ **Integration Matching**: Smart filtering based on Asset Source keywords

## 📚 Documentation

- **[ENTERPRISE_SCALING.md](ENTERPRISE_SCALING.md)** - Comprehensive enterprise scaling guide
  - Performance recommendations for 10,000+ repositories
  - Rate limiting guidelines for different APIs
  - Troubleshooting common issues
  - Best practices for large-scale imports

## Integration Types

Supported integration types:
- `github` - GitHub
- `github-cloud-app` - GitHub Cloud App
- `github-enterprise` - GitHub Enterprise
- `gitlab` - GitLab  
- `azure-repos` - Azure DevOps
- `bitbucket-cloud` - Bitbucket Cloud
- `bitbucket-server` - Bitbucket Server

## 🛠️ Enterprise Support

For organizations processing 10,000+ repositories:

1. **Read**: [ENTERPRISE_SCALING.md](ENTERPRISE_SCALING.md) for detailed guidance
2. **Test**: Use `create_test_data.py` to generate sample data
3. **Tune**: Adjust `--max-workers` and `--rate-limit` for your environment
4. **Monitor**: Watch progress output for performance insights
- `github-enterprise` - GitHub Enterprise

## Example Workflow

1. **Prepare your CSV** with Application names and Repository URLs
2. **Phase 1**: `python create_orgs.py --group-id abc123 --csv-file data.csv`
3. **Create organizations** in Snyk using the generated JSON file
4. **Phase 2**: `python create_targets.py --group-id abc123 --csv-file data.csv`  
5. **Import repositories** in Snyk using the generated targets file
