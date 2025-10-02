from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, flash
from flask_executor import Executor
import json
import os
from datetime import datetime
from pathlib import Path
import pandas as pd
from main import run_validation_pipeline, load_config

app = Flask(__name__)
app.secret_key = 'ipo-validation-secret-key-2025'
executor = Executor(app)

VALIDATIONS_DIR = Path('validations')
METADATA_FILE = VALIDATIONS_DIR / 'metadata.json'

VALIDATIONS_DIR.mkdir(exist_ok=True)
if not METADATA_FILE.exists():
    METADATA_FILE.write_text(json.dumps({'validations': []}, indent=2))


def load_metadata():
    try:
        with open(METADATA_FILE, 'r') as f:
            content = f.read()
            if not content.strip():
                return {'validations': []}
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return {'validations': []}


def save_metadata(metadata):
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)


def run_validation_job(validation_id, config):
    metadata = load_metadata()
    validation_entry = next((v for v in metadata['validations'] if v['id'] == validation_id), None)
    
    if not validation_entry:
        return
    
    try:
        validation_entry['status'] = 'running'
        save_metadata(metadata)
        
        start_time = datetime.now()
        results = run_validation_pipeline(config)
        end_time = datetime.now()
        
        output_path = VALIDATIONS_DIR / f'{validation_id}.csv'
        results.to_csv(output_path, index=False)
        
        validation_entry['status'] = 'completed'
        validation_entry['total_records'] = len(results)
        validation_entry['critical_issues'] = len(results[results['variance_category'].isin(['MISSING_FROM_IPO', 'MISSING_FROM_USAGE'])])
        validation_entry['execution_time'] = (end_time - start_time).total_seconds()
        save_metadata(metadata)
        
    except Exception as e:
        validation_entry['status'] = 'failed'
        validation_entry['error'] = str(e)
        save_metadata(metadata)


@app.route('/')
def index():
    config = load_config()
    error = request.args.get('error')
    return render_template('index.html', config=config, error=error)


@app.route('/start-validation', methods=['POST'])
def start_validation():
    config = load_config()
    validation_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    metadata = load_metadata()
    validation_entry = {
        'id': validation_id,
        'timestamp': datetime.now().isoformat(),
        'status': 'pending',
        'date_range': {
            'start': config['validation']['start_date'],
            'end': config['validation']['end_date']
        },
        'companies': config['validation']['companies']
    }
    metadata['validations'].insert(0, validation_entry)
    save_metadata(metadata)
    
    executor.submit(run_validation_job, validation_id, config)
    
    return redirect(url_for('view_validation', validation_id=validation_id))


@app.route('/validations')
def validations_dashboard():
    metadata = load_metadata()
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    validations = metadata['validations']
    total = len(validations)
    start = (page - 1) * per_page
    end = start + per_page
    
    paginated = validations[start:end]
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('dashboard.html', 
                         validations=paginated, 
                         page=page, 
                         total_pages=total_pages)


@app.route('/validations/<validation_id>')
def view_validation(validation_id):
    metadata = load_metadata()
    validation = next((v for v in metadata['validations'] if v['id'] == validation_id), None)
    
    if not validation:
        flash('Validation not found', 'error')
        return redirect(url_for('validations_dashboard'))
    
    if validation['status'] != 'completed':
        return render_template('results.html', validation=validation, status=validation['status'])
    
    csv_path = VALIDATIONS_DIR / f'{validation_id}.csv'
    if not csv_path.exists():
        flash('Results file not found', 'error')
        return redirect(url_for('validations_dashboard'))
    
    df = pd.read_csv(csv_path)
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
        'total_variances': len(df[df['variance_category'] != 'PERFECT_MATCH']),
        'perfect_matches': len(df[df['variance_category'] == 'PERFECT_MATCH']),
        'critical_issues': len(df[df['variance_category'].isin(['MISSING_FROM_IPO', 'MISSING_FROM_USAGE'])]),
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
    # Using StoneAge official color palette
    colors = {
        'PERFECT_MATCH': '#00a65a',      # success.main
        'MISSING_FROM_IPO': '#e4104e',   # danger.main
        'MISSING_FROM_USAGE': '#f1d622',  # warning.main
        'MORE_IN_USAGE': '#53acdb',      # info.main
        'MORE_IN_IPO': '#6D7878'         # common.border
    }
    
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
    metadata = load_metadata()
    validation = next((v for v in metadata['validations'] if v['id'] == validation_id), None)
    
    if not validation:
        return jsonify({'status': 'not_found'}), 404
    
    return jsonify({
        'status': validation['status'],
        'error': validation.get('error')
    })


@app.route('/download/<validation_id>')
def download_validation(validation_id):
    csv_path = VALIDATIONS_DIR / f'{validation_id}.csv'
    
    if not csv_path.exists():
        flash('File not found', 'error')
        return redirect(url_for('validations_dashboard'))
    
    return send_file(csv_path, 
                     as_attachment=True, 
                     download_name=f'validation_{validation_id}.csv')


if __name__ == '__main__':
    app.run(debug=True, port=5000)

