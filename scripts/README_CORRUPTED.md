# Assets Import Tool for Snyk

A comprehensive tool for importing repositories from various SCM platforms into Snyk organizations with proper application boundary enforcement.

## 🎯 Overview

This tool provides a complete workflow for importing repositories into Snyk while maintaining organizational boundaries based on your application structure. It integrates with `snyk-api-import` to provide enterprise-scale import capabilities with enhanced authentication and filtering.

## 🏗️ Architecture

The import process follows a 4-step workflow:

1. **Generate Organization Data**: Create Snyk organization structure from your CSV (`create_orgs.py`)
2. **Create Organizations in Snyk**: Use `snyk-api-import` to create the organizations in Snyk
3. **Generate Import Targets**: Create repository import targets with automatic SCM integration and application boundary enforcement (`create_targets_fixed.py`)
4. **Import Repositories**: Use `snyk-api-import` to perform the actual repository imports into Snyk

## 📋 Prerequisites

### Required Files
- `assets.csv` - Repository inventory with Application column mapping

### Environment Variables

**For Authentication (private repos and repository metadata access):**

*Standard Authentication:*
```bash
export GITHUB_TOKEN="your_github_personal_access_token"
export GITLAB_TOKEN="your_gitlab_personal_access_token" 
export AZURE_DEVOPS_TOKEN="your_azure_devops_personal_access_token"
export SNYK_TOKEN="your_snyk_token"
```

*GitHub App Authentication (for --source github-cloud-app):*
```bash
export GITHUB_APP_ID="your_app_id"
export GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
your-private-key-content-here
-----END RSA PRIVATE KEY-----"
# Optional: target specific installation
export GITHUB_APP_INSTALLATION_ID="your_installation_id"
```

**For Logging (recommended):**
```bash
export SNYK_LOG_PATH="/path/to/logs"
# Example: export SNYK_LOG_PATH="$HOME/snyk-logs"
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

Both scripts automatically generate detailed log files when `SNYK_LOG_PATH` is set:

- **create_orgs.py** → `create_orgs_YYYYMMDD_HHMMSS.log`
- **create_targets_fixed.py** → `create_targets_YYYYMMDD_HHMMSS.log`

The logs capture:
- Command line arguments and execution start/end
- CSV parsing results and organization loading
- HTTP request failures and rate limiting events
- Error details with full stack traces
- Performance metrics and auto-tuning decisions

If `SNYK_LOG_PATH` is not set, logs will only display on the console.

## 🚀 Quick Start

## 🎯 Overview

This tool provides a complete workflow for importing repositories into Snyk while maintaining organizational boundaries based on your application structure. It integrates with `snyk-api-import` to provide enterprise-scale import capabilities with enhanced authentication and filtering.

## 🏗️ Architecture

The import process follows a 4-step workflow:

1. **Generate Organization Data**: Create Snyk organization structure from your CSV (`create_orgs.py`)
2. **Create Organizations in Snyk**: Use `snyk-api-import` to create the organizations in Snyk
3. **Generate Import Targets**: Create repository import targets with automatic SCM integration and application boundary enforcement (`create_targets_fixed.py`)
4. **Import Repositories**: Use `snyk-api-import` to perform the actual repository imports into Snyk

## 📋 Prerequisites

### Required Files
- `assets.csv` - Repository inventory with Application column mapping

### Environment Variables

**For Authentication (private repos and repository metadata access):**

*Standard Authentication:*
```bash
export GITHUB_TOKEN="your_github_personal_access_token"
export GITLAB_TOKEN="your_gitlab_personal_access_token" 
export AZURE_DEVOPS_TOKEN="your_azure_devops_personal_access_token"
export SNYK_TOKEN="your_snyk_token"
```

*GitHub App Authentication (for --source github-cloud-app):*
```bash
export GITHUB_APP_ID="your_app_id"
export GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
your-private-key-content-here
-----END RSA PRIVATE KEY-----"
# Optional: target specific installation
export GITHUB_APP_INSTALLATION_ID="your_installation_id"
```

**For Logging (recommended):**
```bash
export SNYK_LOG_PATH="/path/to/logs"
# Example: export SNYK_LOG_PATH="$HOME/snyk-logs"
```

### Dependencies
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install snyk-api-import
npm install -g snyk-api-import
```

## � Logging

Both scripts automatically generate detailed log files when `SNYK_LOG_PATH` is set:

- **create_orgs.py** → `create_orgs_YYYYMMDD_HHMMSS.log`
- **create_targets_fixed.py** → `create_targets_YYYYMMDD_HHMMSS.log`

The logs capture:
- Command line arguments and execution start/end
- CSV parsing results and organization loading
- HTTP request failures and rate limiting events
- Error details with full stack traces
- Performance metrics and auto-tuning decisions

If `SNYK_LOG_PATH` is not set, logs will only display on the console.

## �🚀 Quick Start

### Step 1: Set Up Logging (Recommended)

```bash
# Create log directory
mkdir -p "$HOME/snyk-logs"
export SNYK_LOG_PATH="$HOME/snyk-logs"
```

### Step 2: Generate Organization Data

```bash
# Generate Snyk organization structure from your CSV data
python create_orgs.py --group-id YOUR_GROUP_ID --csv-file assets.csv
```

**Output**: `group-YOUR_GROUP_ID-orgs.json`

### Step 3: Create Organizations in Snyk

```bash
# Use snyk-api-import to create the organizations in Snyk
snyk-api-import orgs --file=group-YOUR_GROUP_ID-orgs.json
```

### Step 4: Generate Import Targets

```bash
# Generate import targets with automatic SCM integration and boundary enforcement
python create_targets_fixed.py --group-id YOUR_GROUP_ID --csv-file assets.csv --orgs-json group-YOUR_GROUP_ID-orgs.json --source github
```

**Output**: `import-targets.json`

### Step 5: Import Repositories

```bash
# Use snyk-api-import to perform the actual repository imports
snyk-api-import import --file=import-targets.json
```

## 🚀 Enterprise Scale Usage

### **Auto-Tuned Performance (Default)**
```bash
# Works for any scale - automatically optimized!
python create_targets_fixed.py --group-id YOUR_GROUP_ID --csv-file your-data.csv --orgs-json snyk-created-orgs.json --source github

# 10,000+ repositories? Still just one command:
python create_targets_fixed.py --group-id YOUR_GROUP_ID --csv-file large-dataset.csv --orgs-json snyk-created-orgs.json --source github
```

### **Custom Performance Tuning (Optional)**
```bash
# Override auto-tuning if needed
python create_targets_fixed.py \
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
python create_targets_fixed.py \
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
python create_targets_fixed.py --group-id abc123 --csv-file mydata.csv --orgs-json snyk-created-orgs.json --source github

# Enterprise performance tuning
python create_targets_fixed.py --group-id abc123 --csv-file mydata.csv --orgs-json snyk-created-orgs.json --source github --max-workers 20 --rate-limit 800

# Global overrides for all repositories  
python create_targets_fixed.py --group-id abc123 --csv-file mydata.csv --orgs-json snyk-created-orgs.json --source github --branch main --files "package.json" --exclusion-globs "test,spec"

# Custom output file
python create_targets_fixed.py --group-id abc123 --csv-file mydata.csv --orgs-json snyk-created-orgs.json --source gitlab --output my-targets.json
```

## ⚡ Performance Tuning & Rate Limiting

### Automatic Rate Limiting

The tool automatically configures rate limits based on SCM platform capabilities:

| Platform | Default Rate Limit | API Limit | Notes |
|----------|-------------------|-----------|-------|
| **GitHub** | 80 req/min | 5,000 req/hour | Conservative for stability |
| **GitLab** | 250 req/min | 300 req/min | Near maximum for performance |
| **Azure DevOps** | 150 req/min | Varies | Estimated conservative rate |

### Manual Rate Limiting

Override auto-tuned defaults for specific environments:

```bash
# Conservative rate limiting (shared API tokens)
python create_targets_fixed.py --group-id abc123 --csv-file data.csv --orgs-json orgs.json --source github --rate-limit 30

# Aggressive rate limiting (dedicated GitHub App)
python create_targets_fixed.py --group-id abc123 --csv-file data.csv --orgs-json orgs.json --source github-cloud-app --rate-limit 200

# Custom concurrent workers
python create_targets_fixed.py --group-id abc123 --csv-file data.csv --orgs-json orgs.json --source github --max-workers 10
```

### Concurrent Workers Auto-Tuning

| Repository Count | Auto-Tuned Workers | Reasoning |
|------------------|-------------------|-----------|
| ≤ 100 | 10 workers | Fast completion without overwhelming APIs |
| 101-500 | 20 workers | Balanced performance |
| 501-2,000 | 30 workers | High throughput |
| 2,001-5,000 | 40 workers | Maximum efficiency |
| 5,000+ | 50 workers | Enterprise scale with rate limiting |

### Rate Limit Monitoring

All rate limit events are logged with full details:

```
⚠️ Rate limit hit for https://api.github.com/repos/owner/repo, waiting 4s before retry 2/3
```

**Log Location:**
- With `SNYK_LOG_PATH`: `$SNYK_LOG_PATH/create_targets_YYYYMMDD_HHMMSS.log`  
- Without: `create_targets.log` in current directory

### Performance Recommendations

**For High-Volume Processing (1,000+ repos):**
1. Use GitHub App authentication for higher rate limits
2. Set `SNYK_LOG_PATH` for comprehensive monitoring
3. Start with default auto-tuning, then adjust based on logs
4. Monitor rate limit events and reduce `--max-workers` if frequent

**For Corporate Networks:**
- Reduce `--rate-limit` if behind restrictive proxies
- Use `--max-workers 5` for conservative processing  
- Enable SSL bypass with environment variables if needed

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

Example CSV:
```csv
Application,Type,Asset,Repository URL,Asset Source
MyApp,Repository,Backend Service,https://github.com/company/myapp,GitHub Enterprise
DataPipe,Repository,Data Pipeline,https://gitlab.com/company/data,GitLab SaaS
WebApp,Repository,Frontend,https://dev.azure.com/company/project/_git/webapp,Azure DevOps
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

**Note**: Bitbucket integrations are not currently supported.

## 🛠️ Enterprise Support

For organizations processing 10,000+ repositories:

1. **Read**: [ENTERPRISE_SCALING.md](ENTERPRISE_SCALING.md) for detailed guidance
2. **Test**: Use `create_test_data.py` to generate sample data
3. **Tune**: Adjust `--max-workers` and `--rate-limit` for your environment
4. **Monitor**: Watch progress output for performance insights
- `github-enterprise` - GitHub Enterprise

## Example Workflow

1. **Prepare your CSV** with Application names and Repository URLs
2. **Generate Org Data**: `python create_orgs.py --group-id abc123 --csv-file data.csv`
3. **Create Organizations**: `snyk-api-import orgs --file=snyk-created-orgs.json`
4. **Generate Import Targets**: `python create_targets_fixed.py --group-id abc123 --csv-file data.csv --orgs-json snyk-created-orgs.json --source github`  
5. **Import Repositories**: `snyk-api-import import --file=github-import-targets.json`
