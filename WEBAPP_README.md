# IPO Validation Flask Webapp

## Quick Start

### 1. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 2. Run the Application

```powershell
python app.py
```

The app will start at: **http://localhost:5000**

### 3. Using the Webapp

#### Home Page (/)
- View current validation configuration
- Click "Start Validation Check" to run a new validation
- Any errors will be displayed here

#### Running a Validation
1. Click "Start Validation Check"
2. You'll be redirected to the results page
3. A loading spinner shows while validation runs (10-30 seconds)
4. Page auto-refreshes when complete

#### Results Page (/validations/<id>)
- **Summary Cards**: Total records, perfect matches, variances, critical issues
- **Breakdown Tables**: Variance categories and company distribution
- **Interactive Chart**: Timeline stacked bar chart
  - Filter by date range (start/end dates)
  - Filter by location (checkboxes)
  - Hover over bars for detailed tooltips
- **Download Button**: Get complete results as CSV

#### Validations Dashboard (/validations)
- View all past validation runs
- Paginated (20 per page)
- Click any validation to view results
- Download CSV directly from cards

## Features

✅ Background validation execution (non-blocking)  
✅ Real-time status polling  
✅ Interactive Chart.js visualization  
✅ Client-side filtering (date + location)  
✅ Responsive design (mobile-friendly)  
✅ Error handling with user feedback  
✅ Pagination for large validation history  
✅ StoneAge burnt orange branding  

## File Structure

```
IPO_Validation_2/
├── app.py                    # Flask application
├── templates/
│   ├── base.html            # Base template
│   ├── index.html           # Home page
│   ├── dashboard.html       # Validations list
│   └── results.html         # Results with chart
├── static/
│   ├── css/style.css        # Styling
│   └── js/charts.js         # Chart logic & filters
├── validations/             # Auto-generated validation results
│   ├── metadata.json        # Tracking all runs
│   └── *.csv               # Individual results
└── config.json              # Pipeline configuration
```

## Deployment Notes

### For Railway Deployment:
1. Railway will automatically detect Flask app
2. Ensure `Procfile` exists: `web: python app.py`
3. Set environment variable: `FLASK_ENV=production`
4. Railway will use port from `$PORT` environment variable

### For Production:
- Change `app.run(debug=True)` to `app.run(debug=False)`
- Use a production WSGI server (Gunicorn)
- Set a secure `app.secret_key`

## Troubleshooting

**Validation stuck on "running":**
- Check terminal/console for Python errors
- Database connection may have failed
- Check `validations/metadata.json` for error message

**Chart not displaying:**
- Ensure Chart.js CDN is accessible
- Check browser console for JavaScript errors
- Verify CSV file was created in `validations/` directory

**"File not found" when downloading:**
- Validation may have failed
- Check `validations/` directory for CSV file
- Review validation status in dashboard

## Color Scheme

- **Burnt Orange**: #D2691E (primary)
- **White**: #FFFFFF (background)
- **Dark Gray**: #333333 (text)
- **Success Green**: #28A745 (perfect matches)
- **Error Red**: #DC3545 (critical issues)
- **Warning Orange**: #FFC107 (warnings)

