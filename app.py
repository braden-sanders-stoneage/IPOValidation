from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, flash
from flask_executor import Executor
import json
import os
from datetime import datetime
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

from utils.main import load_config
from utils.validator import load_metadata, save_metadata, run_validation_job, VALIDATIONS_DIR, METADATA_FILE
from utils.scheduler import init_scheduler, get_scheduler_info

load_dotenv()

print("\n" + "="*80)
print("IPO VALIDATION SYSTEM - FLASK APPLICATION")
print("="*80)
print(f"[APP] Initializing Flask application...")

app = Flask(__name__)
app.secret_key = 'ipo-validation-secret-key-2025'
executor = Executor(app)

print(f"[APP] Validations directory: {VALIDATIONS_DIR.absolute()}")
print(f"[APP] Metadata file: {METADATA_FILE.absolute()}")
print(f"[APP] Flask-Executor initialized for background jobs")

# Initialize scheduler (will be started later if enabled)
scheduler = BackgroundScheduler()
print(f"[APP] BackgroundScheduler initialized")

print("="*80 + "\n")


# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
def index():
    print(f"[ROUTE] GET / - Home page accessed")
    config = load_config()
    error = request.args.get('error')
    if error:
        print(f"[ROUTE] Error message to display: {error}")
    
    # Get scheduler info for countdown
    scheduler_info = get_scheduler_info(config)
    
    return render_template('index.html', config=config, error=error, scheduler_info=scheduler_info)


@app.route('/start-validation', methods=['POST'])
def start_validation():
    print("\n" + "="*80)
    print(f"[ROUTE] POST /start-validation - Manual validation triggered")
    print("="*80)
    
    config = load_config()
    validation_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    print(f"[ROUTE] Created validation ID: {validation_id}")
    print(f"[ROUTE] Configuration:")
    print(f"  - Date range: {config['validation']['start_date']} to {config['validation']['end_date']}")
    print(f"  - Companies: {', '.join(config['validation']['companies'])}")
    
    metadata = load_metadata()
    validation_entry = {
        'id': validation_id,
        'timestamp': datetime.now().isoformat(),
        'status': 'pending',
        'date_range': {
            'start': config['validation']['start_date'],
            'end': config['validation']['end_date']
        },
        'companies': config['validation']['companies'],
        'triggered_by': 'manual'
    }
    metadata['validations'].insert(0, validation_entry)
    save_metadata(metadata)
    
    print(f"[ROUTE] Validation entry created in metadata")
    print(f"[ROUTE] Submitting validation job to Flask-Executor (background)")
    
    executor.submit(run_validation_job, validation_id, config)
    
    print(f"[ROUTE] Job submitted successfully - redirecting to results page")
    print("="*80 + "\n")
    
    return redirect(url_for('view_validation', validation_id=validation_id))


@app.route('/validations')
def validations_dashboard():
    print(f"[ROUTE] GET /validations - Dashboard accessed")
    metadata = load_metadata()
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    validations = metadata['validations']
    total = len(validations)
    start = (page - 1) * per_page
    end = start + per_page
    
    paginated = validations[start:end]
    total_pages = (total + per_page - 1) // per_page
    
    print(f"[ROUTE] Displaying {len(paginated)} validations (page {page} of {total_pages}, {total} total)")
    
    return render_template('dashboard.html', 
                         validations=paginated, 
                         page=page, 
                         total_pages=total_pages)


@app.route('/validations/<validation_id>')
def view_validation(validation_id):
    print(f"[ROUTE] GET /validations/{validation_id} - Viewing validation results")
    metadata = load_metadata()
    validation = next((v for v in metadata['validations'] if v['id'] == validation_id), None)
    
    if not validation:
        print(f"[ROUTE] ✗ Validation not found: {validation_id}")
        flash('Validation not found', 'error')
        return redirect(url_for('validations_dashboard'))
    
    print(f"[ROUTE] Validation status: {validation['status']}")
    
    if validation['status'] != 'completed':
        print(f"[ROUTE] Validation not completed yet - showing status page")
        return render_template('results.html', validation=validation, status=validation['status'])
    
    csv_path = VALIDATIONS_DIR / f'{validation_id}.csv'
    if not csv_path.exists():
        print(f"[ROUTE] ✗ Results file not found: {csv_path}")
        flash('Results file not found', 'error')
        return redirect(url_for('validations_dashboard'))
    
    print(f"[ROUTE] Loading results from: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"[ROUTE] Loaded {len(df):,} records, processing for display...")
    
    df['period'] = pd.to_datetime(df['period'])
    df['month'] = df['period'].dt.strftime('%Y-%m')
    
    # For chart: group by month, location, and variance category
    chart_detail = df.groupby(['month', 'location', 'variance_category']).size().reset_index(name='count')
    
    # Convert to list of dicts for JavaScript
    chart_raw_data = chart_detail.to_dict('records')
    
    locations = sorted(df['location'].unique().tolist())
    companies = sorted(df['company'].unique().tolist())
    
    total_records = len(df)
    variance_counts = df['variance_category'].value_counts().to_dict()
    company_counts = df['company'].value_counts().to_dict()
    location_counts = df['location'].value_counts().to_dict()
    
    # Variance by company breakdown
    variance_by_company = {}
    for company in companies:
        company_df = df[df['company'] == company]
        company_total = len(company_df)
        variance_by_company[company] = {
            'total': company_total,
            'breakdown': company_df['variance_category'].value_counts().to_dict()
        }
    
    # Variance by location breakdown
    variance_by_location = {}
    for location in locations:
        location_df = df[df['location'] == location]
        location_total = len(location_df)
        variance_by_location[location] = {
            'total': location_total,
            'breakdown': location_df['variance_category'].value_counts().to_dict()
        }
    
    # Variance statistics
    variance_stats = {
        'mean': float(df['absolute_variance'].mean()),
        'median': float(df['absolute_variance'].median()),
        'max': float(df['absolute_variance'].max()),
        'total': float(df['absolute_variance'].sum())
    }
    
    summary_stats = {
        'total_records': total_records,
        'total_variances': len(df[df['variance_category'] != 'Perfect Match']),
        'perfect_matches': len(df[df['variance_category'] == 'Perfect Match']),
        'critical_issues': len(df[df['variance_category'].isin(['Missing From IP&O', 'Missing From Usage'])]),
        'variance_counts': variance_counts,
        'company_counts': company_counts,
        'location_counts': location_counts,
        'variance_by_company': variance_by_company,
        'variance_by_location': variance_by_location,
        'variance_stats': variance_stats,
        'date_range': {
            'start': df['period'].min().strftime('%Y-%m-%d'),
            'end': df['period'].max().strftime('%Y-%m-%d')
        },
        'total_months': df['period'].nunique()
    }
    
    # Send raw data to JavaScript for client-side aggregation
    colors = {
        'Perfect Match': '#00a65a',      # Green
        'Missing From IP&O': '#e4104e',  # Red
        'Missing From Usage': '#ff8c00', # Orange
        'More In IP&O': '#4169e1',       # Blue
        'More In Usage': '#9370db'       # Purple
    }
    
    print(f"[ROUTE] Rendering results page with summary statistics")
    
    return render_template('results.html', 
                         validation=validation, 
                         status='completed',
                         chart_raw_data=json.dumps(chart_raw_data),
                         chart_colors=json.dumps(colors),
                         locations=locations,
                         companies=companies,
                         summary=summary_stats)


@app.route('/api/status/<validation_id>')
def check_status(validation_id):
    print(f"[API] GET /api/status/{validation_id} - Status check")
    metadata = load_metadata()
    validation = next((v for v in metadata['validations'] if v['id'] == validation_id), None)
    
    if not validation:
        print(f"[API] ✗ Validation not found: {validation_id}")
        return jsonify({'status': 'not_found'}), 404
    
    print(f"[API] Status: {validation['status']}")
    
    return jsonify({
        'status': validation['status'],
        'error': validation.get('error')
    })


@app.route('/download/<validation_id>')
def download_validation(validation_id):
    print(f"[ROUTE] GET /download/{validation_id} - CSV download requested")
    csv_path = VALIDATIONS_DIR / f'{validation_id}.csv'
    
    if not csv_path.exists():
        print(f"[ROUTE] ✗ File not found: {csv_path}")
        flash('File not found', 'error')
        return redirect(url_for('validations_dashboard'))
    
    file_size = csv_path.stat().st_size / 1024  # KB
    print(f"[ROUTE] Sending file: {csv_path.name} ({file_size:.1f} KB)")
    
    return send_file(csv_path, 
                     as_attachment=True, 
                     download_name=f'validation_{validation_id}.csv')


# ============================================================================
# APPLICATION STARTUP
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*80)
    print("STARTING FLASK APPLICATION")
    print("="*80)
    print(f"[APP] Debug mode: True")
    print(f"[APP] Port: 5000")
    print(f"[APP] Access URL: http://localhost:5000")
    print(f"[APP] Press CTRL+C to quit")
    print("="*80 + "\n")
    
    # Initialize scheduler (if enabled in config)
    init_scheduler(scheduler)
    
    app.run(debug=True, port=5000)

