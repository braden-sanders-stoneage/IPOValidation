# IPO Validation System

A comprehensive Flask-based web application for validating data integrity between Epicor ERP usage data and IP&O (Inventory Planning & Optimization) forecast data. This system identifies discrepancies, categorizes variances, and provides interactive visualizations for data quality analysis.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Data Sources](#data-sources)
- [Pipeline Architecture](#pipeline-architecture)
- [Webapp Features](#webapp-features)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

### Purpose

This application validates that actual material usage data from Epicor ERP matches the forecast data sent to IP&O forecasting software. It identifies:

- **Missing Parts**: Parts with usage but not in IP&O (critical blind spots)
- **Data Sync Issues**: Parts that stopped appearing in IP&O
- **Forecast Variances**: Differences between actual and forecasted usage
- **Data Quality Problems**: Mismatches requiring investigation

### Key Benefits

✅ **Automated Validation**: Run validations on-demand with single click  
✅ **Background Processing**: Non-blocking execution with real-time status updates  
✅ **Interactive Visualizations**: Filter and explore results by date, location, and variance type  
✅ **Historical Tracking**: All validation runs saved with full audit trail  
✅ **CSV Export**: Download complete results for analysis in Excel or Power BI  

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Access to StoneAge SQL Server database (SAI-AZRDW02)
- ODBC Driver 17 for SQL Server
- SQL Server authentication credentials (stored in .env file)

### Installation

1. **Install dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

2. **Create .env file** in the project root with database credentials:
   ```
   DB_USERNAME=your_username
   DB_PASSWORD=your_password
   ```

3. **Verify database configuration** (config.json)
   ```json
   {
     "database": {
       "server": "SAI-AZRDW02",
       "database": "MULE_STAGE",
       "port": 1433,
       "driver": "ODBC Driver 17 for SQL Server"
     }
   }
   ```

4. **Run the application**
   ```powershell
   python app.py
   ```

5. **Open browser**
   ```
   http://localhost:5000
   ```

### Scheduled Validations (Optional)

**Purpose:** Automatically run validations on a recurring schedule

**The scheduler is integrated into the Flask app and starts automatically when enabled.**

#### Configuration Options

The scheduler supports two modes:

**1. Monthly Schedule (Production)**
```json
{
  "scheduler": {
    "enabled": true,
    "schedule_type": "monthly",
    "monthly_day": 1,
    "monthly_hour": 8,
    "monthly_minute": 0,
    "timezone": "America/Denver"
  }
}
```
- Runs on the 1st of each month at 8:00 AM
- Perfect for monthly reporting cycles
- Simple and predictable

**2. Testing Schedule (Development)**
```json
{
  "scheduler": {
    "enabled": true,
    "schedule_type": "testing",
    "testing_cron": "*/5 * * * *",
    "timezone": "America/Denver"
  }
}
```
- Uses custom cron expression for flexible testing
- Examples:
  - `"*/5 * * * *"` - Every 5 minutes
  - `"0 */2 * * *"` - Every 2 hours
  - `"0 9 * * 1-5"` - Weekdays at 9 AM

#### Starting the Scheduler

Simply start Flask - scheduler runs automatically in background:
```powershell
python app.py
```

The scheduler will display its configuration on startup and run validations according to the schedule.

---

## 📊 Data Sources

### 1. PartUsage Table

**Source**: Epicor ERP actual material usage  
**Location**: `MULE_STAGE.dbo.PartUsage`  
**Grain**: One row per company/plant/part/month combination

**Key Fields**:
- `company_plant_part` - Composite key (e.g., "SAINC_MfgSys_ABX 326")
- `endOfMonth` - Period end date
- `ICUsage` - Intercompany usage quantity
- `IndirectUsage` - Indirect material usage quantity
- `DirectUsage` - Direct material usage quantity
- `RentUsage` - Rental usage quantity
- Transaction counts for each usage type

**Business Logic**:
- Represents actual material consumption from ERP system
- Source of truth for what was actually used
- Includes both manufactured and purchased parts

### 2. IPOValidation Table

**Source**: Forecast data sent to IP&O software  
**Location**: `MULE_STAGE.dbo.IPOValidation`  
**Grain**: One row per company/location/part/period combination

**Key Fields**:
- `Company` - Company code (SAINC, SAUK, SANL)
- `Location` - Business location name
- `Product` - Part number
- `Period` - Forecast period date
- `Qty` - Forecasted usage quantity

**Business Logic**:
- Represents what was communicated to forecasting system
- Should match actual usage (when properly configured)
- Missing parts indicate forecasting blind spots

### 3. Part Metadata (sai_dw.Erp.Part)

**Purpose**: Exclusion criteria and part attributes  
**Location**: `sai_dw.Erp.Part` and `sai_dw.Erp.PartPlant`

**Key Fields**:
- `ClassID` - Material classification (PUR, MFG, RAW, CSM, etc.)
- `InActive` - Part lifecycle status
- `Runout` - Phase-out indicator
- `NonStock` - Stocking status
- `ProdCode` - Product category

---

## 🔧 Pipeline Architecture

### 7-Step Validation Process

#### STEP 1: Database Connection
- Establish SQL Server connection using Windows Authentication
- Connect to MULE_STAGE database
- Initialize SQLAlchemy engine

#### STEP 2: Data Extraction
- Query `PartUsage` table for date range
- Query `IPOValidation` table for date range
- Optionally query part metadata for exclusions

#### STEP 3: Normalize PartUsage

**Parsing**:
```
"SAINC_MfgSys_ABX 326" → Company: SAINC, Plant: MfgSys, Part: ABX 326
```

**Location Mapping**:
| Company | Plant | → | Location |
|---------|-------|---|----------|
| SAINC | SAILA | → | StoneAge Louisiana |
| SAINC | SAIOH, SAICTN | → | StoneAge Ohio |
| SAINC | SAITX | → | StoneAge Texas |
| SAINC | MfgSys | → | StoneAge, Inc. |
| SAUK | MfgSys | → | StoneAge Europe Ltd |
| SANL | MfgSys | → | StoneAge Netherlands B.V. |

**Usage Calculation**:
- **SAINC MfgSys**: `ICUsage + IndirectUsage + DirectUsage`
- **All Other Locations**: `DirectUsage` only

**Date Normalization**:
- Convert all dates to end-of-month format
- Ensures consistent join with IPOValidation

**Output Schema**:
```
company, location, plant, part_num, period, actual_usage
```

#### STEP 4: Normalize IPOValidation

**Transformations**:
- Standardize column names (lowercase with underscores)
- Normalize dates to end-of-month
- Rename columns for consistency

**Output Schema**:
```
company, location, part_num, period, ipo_usage
```

#### STEP 5: Apply Exclusions (Optional)

**When Enabled** (`apply_exclusions: true`):

Parts are excluded if ANY of the following are true:

| Criterion | Rule | Reason |
|-----------|------|--------|
| **NonStock** | `= True` | Non-stocked items aren't forecasted |
| **InActive** | `= True` | Inactive parts shouldn't be in IP&O |
| **Runout** | `= True` | Phase-out parts excluded |
| **ClassID** | `IN ('RAW', 'CSM')` | Raw materials and consumables |
| **Low Usage** | `≤2 units in 12 months` | Insufficient history for forecasting |

**When Disabled** (`apply_exclusions: false`):
- All parts are validated (current default)
- Results may include parts that should be filtered
- Useful for comprehensive data quality assessment

#### STEP 6: Compare Datasets

**Join Logic**:
```sql
FULL OUTER JOIN ON (company, location, part_num, period)
```

**Variance Calculation**:
```python
variance = ipo_usage - actual_usage
variance_percent = |variance| / actual_usage * 100
absolute_variance = |variance|
```

**Edge Cases**:
- Both zero → `variance_percent = 0%` (perfect match)
- Actual is zero, IPO has data → `variance_percent = 999.99` (flag)
- IPO is zero, Actual has data → `variance_percent = -999.99` (flag)

**Results Include**:
- All records from both sources (even if only in one)
- Records unique to PartUsage (missing from IP&O)
- Records unique to IPOValidation (overforecasted)
- Records in both systems (variance analysis)

#### STEP 7: Categorize Variances

**Variance Categories**:

| Category | Condition | Severity | Description |
|----------|-----------|----------|-------------|
| **Perfect Match** | actual = ipo (exactly) | ✅ None | Data integrity confirmed |
| **Missing From IP&O** | actual > 0, ipo = 0 | 🔴 Critical | Usage occurred but IP&O got zero (underforecast blind spot) |
| **Missing From Usage** | actual = 0, ipo > 0 | 🟠 High | IP&O has data but no actual usage (overforecast) |
| **More In Usage** | actual > ipo | 🟡 Medium | Actual usage higher than forecast (underforecast) |
| **More In IP&O** | ipo > actual | 🔵 Low | Forecast higher than actual (overforecast) |

---

## 🌐 Webapp Features

### Home Page (/)

**Purpose**: Launch point and configuration display

**Features**:
- Current validation configuration display
  - Date range
  - Companies included
  - Database connection
  - Exclusion status
- Single-click validation launch
- Error message display
- Quick link to validation history

### Validation Execution

**Process**:
1. Click "Start Validation Check"
2. Validation submitted to background executor
3. Redirect to results page with loading spinner
4. Page auto-refreshes every 2 seconds
5. Displays results when complete

**Background Processing**:
- Non-blocking execution (Flask-Executor)
- Status tracked in `validations/metadata.json`
- Real-time status API endpoint
- Automatic error capture and display

### Results Page (/validations/<id>)

**Summary Statistics**:
- Total Records
- Total Variances
- Perfect Matches
- Critical Issues (Missing From IP&O + Missing From Usage)

**Interactive Stacked Bar Chart**:
- Timeline view of variances over months
- Color-coded by variance category
- Percentage labels on segments (when >3% of bar)
- Hover tooltips with detailed counts
- Responsive design with consistent y-axis scaling

**Slicers (Filters)**:
1. **Location Slicer**: Toggle locations on/off
2. **Year Slicer**: Filter by year
3. **Month Slicer**: Filter by month (Jan-Dec)
4. Multi-select enabled (click to toggle)
5. Client-side filtering (instant updates)

**Detailed Breakdowns**:
- Date range summary
- Variance category distribution
- Company breakdown with percentages
- Location breakdown with percentages
- Variance by Company (nested)
- Variance by Location (nested)
- Variance magnitude statistics (mean, median, max)

**Download**:
- Complete results as CSV
- All columns included for detailed analysis
- File naming: `validation_YYYYMMDD_HHMMSS.csv`

### Validation Dashboard (/validations)

**Purpose**: Historical tracking and quick access

**Features**:
- Grid view of all past validations
- Status badges (completed, running, failed)
- Date range and company info
- Record counts and critical issue counts
- Quick actions:
  - View Results
  - Download CSV
  - Check Status (for running validations)
- Pagination (20 per page)
- Empty state with helpful message

**Validation Cards**:
- Validation ID (timestamp-based)
- Timestamp
- Status indicator
- Configuration summary
- Performance metrics (for completed)

---

## ⚙️ Configuration

### config.json Structure

```json
{
  "database": {
    "server": "SAI-AZRDW02",
    "database": "MULE_STAGE",
    "port": 1433,
    "driver": "ODBC Driver 17 for SQL Server"
  },
  "validation": {
    "start_date": "2025-05-01",
    "end_date": "2025-08-31",
    "companies": ["SAINC", "SAUK", "SANL"],
    "excluded_companies": ["SAFR"]
  },
  "mappings": {
    "locations": {
      "SAINC": {
        "SAILA": "StoneAge Louisiana",
        "SAIOH": "StoneAge Ohio",
        "SAICTN": "StoneAge Ohio",
        "SAITX": "StoneAge Texas",
        "MfgSys": "StoneAge, Inc."
      },
      "SANL": {
        "MfgSys": "StoneAge Netherlands B.V."
      },
      "SAUK": {
        "MfgSys": "StoneAge Europe Ltd"
      }
    }
  },
  "rules": {
    "usage_calculation": {
      "sainc_mfgsys_components": ["ICUsage", "IndirectUsage", "DirectUsage"],
      "default_component": "DirectUsage"
    }
  },
  "options": {
    "apply_exclusions": true,
    "output_format": "csv",
    "output_path": "validation_results.csv",
    "enable_notifications": true
  },
  "scheduler": {
    "enabled": false,
    "schedule_type": "monthly",
    "monthly_day": 1,
    "monthly_hour": 8,
    "monthly_minute": 0,
    "testing_cron": "*/5 * * * *",
    "timezone": "America/Denver"
  }
}
```

### Key Configuration Options

**Date Range**:
- `start_date` / `end_date`: Validation period
- Format: YYYY-MM-DD
- Filters both PartUsage and IPOValidation

**Companies**:
- `companies`: List of companies to validate
- `excluded_companies`: Companies to skip (e.g., SAFR not yet in IP&O)

**Exclusions**:
- `apply_exclusions: true`: Filter out non-forecasted parts
- `apply_exclusions: false`: Validate all parts (shows configuration issues)

**Location Mappings**:
- Add new locations as needed
- Format: `"COMPANY": { "PLANT": "Location Name" }`

**Scheduler** (Optional):
- `enabled`: Set to `true` to enable automated scheduled validations
- `schedule_type`: Choose scheduling mode:
  - `"monthly"` - Run on specific day of month (production)
  - `"testing"` - Use custom cron expression (development)
- **Monthly Mode** (when `schedule_type: "monthly"`):
  - `monthly_day`: Day of month (1-31, default: 1)
  - `monthly_hour`: Hour of day (0-23, default: 8)
  - `monthly_minute`: Minute of hour (0-59, default: 0)
- **Testing Mode** (when `schedule_type: "testing"`):
  - `testing_cron`: Custom cron expression
    - `"*/5 * * * *"` - Every 5 minutes
    - `"0 */2 * * *"` - Every 2 hours
    - `"0 9 * * 1-5"` - Weekdays at 9 AM
- `timezone`: Timezone for scheduling (e.g., `"America/Denver"`, `"UTC"`)
- Scheduler runs automatically when Flask app starts (integrated)

---

## 📁 Project Structure

```
IPO_Validation_2/
├── app.py                      # Flask application and routes
├── scheduler.py                # Scheduled validation runner (optional)
├── config.json                 # Configuration file
├── requirements.txt            # Python dependencies
│
├── utils/                      # Pipeline modules
│   ├── __init__.py
│   ├── main.py                # Pipeline orchestration
│   ├── database.py            # Database connection and queries
│   └── utils.py               # Data transformation functions
│
├── templates/                  # HTML templates (Jinja2)
│   ├── base.html              # Base template with header/footer
│   ├── index.html             # Home page
│   ├── dashboard.html         # Validation history
│   └── results.html           # Results with charts
│
├── static/                     # Static assets
│   ├── css/
│   │   └── style.css          # StoneAge-branded styling
│   └── js/
│       └── charts.js          # Chart.js logic and filtering
│
├── validations/                # Auto-generated (gitignored)
│   ├── metadata.json          # Validation tracking
│   └── *.csv                  # Individual validation results
│
├── tests/examples/             # Investigation templates
│   ├── AI_AGENT_GUIDE.md      # Part investigation methodology
│   ├── README.md              # Examples documentation
│   └── test_template.py       # Investigation script template
│
└── dev/                        # SQL and development files
    └── vw_ipo_validation.sql  # Original SQL view (reference)
```

---

## 🚀 Deployment

### Local Development

```powershell
# Install dependencies
pip install -r requirements.txt

# Run development server (scheduler starts automatically if enabled)
python app.py

# Access at http://localhost:5000
```

### Azure App Service Deployment

This application is configured for deployment to Azure App Service (Linux, Python 3.12).

#### Prerequisites
- Azure App Service created (Basic tier or higher recommended for "Always On")
- GitHub repository connected via Azure Deployment Center
- SQL Server accessible from Azure (may require VNet integration for on-premises databases)

#### Deployment Files
- `startup.sh`: Gunicorn startup command (1 worker for scheduler compatibility)
- `.deployment`: Azure build configuration
- `requirements.txt`: Includes gunicorn for production WSGI server

#### Azure Configuration Steps

1. **Set Environment Variables** (Azure Portal → Configuration → Application Settings):
   ```
   DB_SERVER=SAI-AZRDW02
   DB_NAME=MULE_STAGE
   DB_PORT=1433
   DB_DRIVER=ODBC Driver 17 for SQL Server
   DB_USERNAME=mulesoft.automation
   DB_PASSWORD=your_password
   OUTLOOK_CLIENT_ID=your_outlook_client_id
   OUTLOOK_CLIENT_SECRET=your_outlook_secret
   OUTLOOK_TENANT_ID=your_tenant_id
   OUTLOOK_MAILBOX_ID=dxp@stoneagetools.com
   OUTLOOK_RECIPIENT_EMAIL=your_email@stoneagetools.com
   ```

2. **Set Startup Command** (Configuration → General Settings):
   ```
   /home/site/wwwroot/startup.sh
   ```

3. **Enable Always On** (Configuration → General Settings):
   - Toggle "Always On" to prevent cold starts
   - Requires Basic tier or higher

4. **Deploy**:
   - Push code to GitHub main branch
   - Azure automatically deploys via GitHub Actions
   - Monitor in Deployment Center

5. **Verify**:
   - Check Log Stream for startup messages
   - Visit your app URL
   - Run a test validation

#### Important Notes
- **Workers**: Configured for 1 worker to prevent duplicate scheduler jobs
- **Database Access**: Ensure Azure can reach SAI-AZRDW02 (may need VNet/VPN)
- **Timeouts**: Gunicorn timeout set to 600 seconds for long validations
- **Local Development**: Still works with `python app.py` (Gunicorn only used in Azure)

### Production Deployment (Non-Azure)

**Configuration Changes**:
1. Set `app.secret_key` to a secure random value
2. Change `app.run(debug=True)` to `app.run(debug=False)`
3. Use production WSGI server:
   ```powershell
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

**Environment Variables**:
```
FLASK_ENV=production
FLASK_SECRET_KEY=<secure-random-key>
```

**Database Access**:
- Ensure production server has SQL Server access
- Create .env file with SQL authentication credentials
- Test connection before deployment

**Scheduler (Optional)**:

The scheduler is **integrated into Flask** and starts automatically when enabled.

**For Production (Monthly Reports):**
```json
{
  "scheduler": {
    "enabled": true,
    "schedule_type": "monthly",
    "monthly_day": 1,
    "monthly_hour": 8,
    "monthly_minute": 0,
    "timezone": "America/Denver"
  }
}
```
- Runs on the 1st of each month at 8:00 AM
- Sends email notification automatically

**For Testing/Development:**
```json
{
  "scheduler": {
    "enabled": true,
    "schedule_type": "testing",
    "testing_cron": "*/10 * * * *",
    "timezone": "America/Denver"
  }
}
```
- Runs every 10 minutes for testing
- Easy to verify functionality

**How It Works:**
- Scheduler starts with Flask in a background thread
- No separate process needed
- Scheduled validations run alongside manual web UI validations
- All validations appear in the same dashboard

---

## 🔍 Troubleshooting

### Database Connection Issues

**Error: "Can't open lib 'ODBC Driver 17 for SQL Server'"**

**Solution**: Install ODBC driver
- Windows: https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
- Or update `config.json` to use installed driver

**Error: "Login failed for user"**

**Solution**: Check authentication credentials in .env file
- Verify `DB_USERNAME` is correct
- Verify `DB_PASSWORD` is correct
- Ensure the SQL user has appropriate permissions on MULE_STAGE database

**Error: "Invalid object name 'PartUsage' or 'IPOValidation'"**

**Solution**: Verify database access
- Check table exists in MULE_STAGE database
- Confirm SELECT permissions granted
- Test connection with Azure Data Studio or SSMS

### Validation Issues

**Validation stuck on "running" status**

**Causes**:
- Database connection timeout
- Query taking too long
- Python error in pipeline

**Solutions**:
1. Check terminal/console for error messages
2. Review `validations/metadata.json` for error field
3. Reduce date range for initial testing
4. Verify database performance

**Chart not displaying**

**Causes**:
- Chart.js CDN not accessible
- JavaScript error
- No data in results

**Solutions**:
1. Check browser console for JavaScript errors
2. Verify CSV file created in `validations/` directory
3. Ensure data exists for selected date range
4. Test with different filters

**"File not found" when downloading**

**Causes**:
- Validation failed to complete
- CSV file not created
- File system permissions

**Solutions**:
1. Check validation status in dashboard
2. Look for CSV file in `validations/` directory
3. Review terminal logs for write errors
4. Verify folder permissions

### Performance Issues

**Slow query performance**

**Solutions**:
- Add indexes to PartUsage.endOfMonth and IPOValidation.Period
- Add indexes to company_plant_part composite key
- Reduce date range in config
- Query specific companies only

**High memory usage**

**Solutions**:
- Process data in smaller date ranges
- Use streaming for large datasets
- Increase system memory allocation
- Consider data archival strategy

---

## 📊 Output Schema

### CSV Export Columns

| Column | Type | Description |
|--------|------|-------------|
| `company` | string | Company code (SAINC, SAUK, SANL) |
| `location` | string | Business-friendly location name |
| `part_num` | string | Part number |
| `period` | date | Period end date (last day of month) |
| `actual_usage` | float | Calculated usage from PartUsage |
| `ipo_usage` | float | Usage value sent to IP&O |
| `variance` | float | Difference (ipo_usage - actual_usage) |
| `variance_percent` | float | Percentage variance |
| `absolute_variance` | float | Absolute value of variance |
| `variance_category` | string | Category (Perfect Match, Missing From IP&O, etc.) |

---

## 🎨 Design System

### StoneAge Branding

**Colors**:
- **Burnt Orange**: `#af5d1b` (primary brand color)
- **Dark Gray**: `#333F48` (text and headers)
- **Off-White**: `#F8F9FA` (background)
- **Success Green**: `#00a65a` (Perfect Match)
- **Error Red**: `#e4104e` (Missing From IP&O)
- **Warning Orange**: `#ff8c00` (Missing From Usage)
- **Info Blue**: `#4169e1` (More In IP&O)
- **Purple**: `#9370db` (More In Usage)

**Typography**:
- **Font Family**: Roboto (Google Fonts)
- **Weights**: 400 (regular), 500 (medium), 700 (bold)

---

## 📝 License

Internal use only - StoneAge Manufacturing

---

## 🤝 Support

For issues or questions:
- **Application bugs**: Check terminal logs and browser console
- **Data discrepancies**: Review business rules in config.json
- **Database access**: Contact database administrator
- **Part investigations**: See `tests/examples/AI_AGENT_GUIDE.md`

---

**Built with ❤️ for StoneAge Manufacturing**  
*Clean Python architecture replacing complex SQL views*
