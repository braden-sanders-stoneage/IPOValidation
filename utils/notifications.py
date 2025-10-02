import os
import requests
from datetime import datetime


def get_app_url():
    railway_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN')
    railway_static = os.getenv('RAILWAY_STATIC_URL')
    
    if railway_domain:
        return f"https://{railway_domain}"
    elif railway_static:
        return railway_static
    else:
        return "http://localhost:5000"


def get_access_token():
    tenant_id = os.getenv('OUTLOOK_TENANT_ID')
    client_id = os.getenv('OUTLOOK_CLIENT_ID')
    client_secret = os.getenv('OUTLOOK_CLIENT_SECRET')
    
    if not all([tenant_id, client_id, client_secret]):
        raise ValueError("Missing Outlook API credentials in environment variables")
    
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    
    token_data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'https://graph.microsoft.com/.default'
    }
    
    response = requests.post(token_url, data=token_data)
    response.raise_for_status()
    
    return response.json()['access_token']


def build_html_email(validation_id, base_url):
    results_url = f"{base_url}/validations/{validation_id}"
    download_url = f"{base_url}/download/{validation_id}"
    
    # StoneAge Design System Colors (from style.css)
    burnt_orange = "#af5d1b"
    burnt_orange_dark = "#8a4a16"
    text_dark = "#333F48"
    text_main = "#4d4d4d"
    text_light = "#666666"
    off_white = "#F8F9FA"
    white = "#FFFFFF"
    success_green = "#00a65a"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta name="color-scheme" content="light dark">
        <meta name="supported-color-schemes" content="light dark">
    </head>
    <body style="margin: 0; padding: 0; background-color: {off_white}; font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: {off_white};">
            <tr>
                <td style="padding: 40px 20px;">
                    <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: {white}; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" cellspacing="0" cellpadding="0" border="0">
                        
                        <!-- Header -->
                        <tr>
                            <td style="background-color: {text_dark}; padding: 30px; text-align: center; border-radius: 8px 8px 0 0;">
                                <h2 style="margin: 0; font-size: 22px; font-weight: 500; color: {white}; letter-spacing: 0.5px; font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">
                                    StoneAge Tools
                                </h2>
                                <p style="margin: 8px 0 0 0; font-size: 13px; color: {off_white}; letter-spacing: 0.5px; font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">
                                    IPO Validation System
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px 30px; background-color: {white};">
                                <h1 style="margin: 0 0 10px 0; font-size: 32px; font-weight: 500; color: {burnt_orange}; font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">
                                    ✓ Validation Complete
                                </h1>
                                
                                <p style="margin: 0 0 40px 0; font-size: 16px; line-height: 1.6; color: {text_main}; font-weight: 400; font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">
                                    Your IPO validation has finished processing successfully. Click below to view the detailed results and analysis.
                                </p>
                                
                                <!-- Buttons -->
                                <table role="presentation" style="width: 100%; margin: 0 0 30px 0;" cellspacing="0" cellpadding="0" border="0">
                                    <tr>
                                        <!-- Primary Button Cell -->
                                        <td style="width: 50%; padding: 0 8px 0 0; text-align: right;">
                                            <a href="{results_url}" style="display: inline-block; width: 100%; max-width: 220px; padding: 14px 28px; background-color: transparent; color: {burnt_orange} !important; text-decoration: none; border-radius: 8px; font-weight: 500; font-size: 16px; font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; border: 2px solid {burnt_orange}; text-align: center; box-sizing: border-box;">
                                                View Results
                                            </a>
                                        </td>
                                        
                                        <!-- Secondary Button Cell -->
                                        <td style="width: 50%; padding: 0 0 0 8px; text-align: left;">
                                            <a href="{download_url}" style="display: inline-block; width: 100%; max-width: 220px; padding: 14px 28px; background-color: transparent; color: {burnt_orange} !important; text-decoration: none; border-radius: 8px; font-weight: 500; font-size: 16px; font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; border: 2px solid {burnt_orange}; text-align: center; box-sizing: border-box;">
                                                Download CSV
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                                
                                <!-- Validation ID (smaller, below buttons) -->
                                <table role="presentation" style="width: 100%; margin: 20px 0 30px 0;" cellspacing="0" cellpadding="0" border="0">
                                    <tr>
                                        <td style="text-align: center; padding: 15px 0; border-top: 1px solid #EBEBEB; border-bottom: 1px solid #EBEBEB;">
                                            <p style="margin: 0 0 4px 0; font-size: 11px; color: {text_light}; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 500; font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">
                                                Validation ID
                                            </p>
                                            <p style="margin: 0; font-size: 13px; font-weight: 500; font-family: 'Courier New', monospace; color: {text_main};">
                                                {validation_id}
                                            </p>
                                        </td>
                                    </tr>
                                </table>
                                
                                <!-- Info Text -->
                                <table role="presentation" style="width: 100%; margin: 0;" cellspacing="0" cellpadding="0" border="0">
                                    <tr>
                                        <td style="padding: 0;">
                                            <p style="margin: 0; font-size: 14px; line-height: 1.6; color: {text_light}; font-weight: 400; font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">
                                                This validation report includes variance analysis, summary statistics, and detailed breakdowns by company and location.
                                            </p>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background-color: {off_white}; padding: 25px 30px; text-align: center; border-radius: 0 0 8px 8px;">
                                <p style="margin: 0 0 10px 0; font-size: 13px; color: {text_light}; font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">
                                    © {datetime.now().year} StoneAge Tools. All rights reserved.
                                </p>
                                <p style="margin: 0;">
                                    <a href="{base_url}" style="color: {burnt_orange}; text-decoration: none; font-size: 14px; font-weight: 500; font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">
                                        IPO Validation Dashboard
                                    </a>
                                </p>
                            </td>
                        </tr>
                        
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    return html


def send_validation_notification(validation_id):
    try:
        print(f"[EMAIL] Preparing to send notification for validation {validation_id}...")
        
        mailbox_id = os.getenv('OUTLOOK_MAILBOX_ID')
        recipient_emails = os.getenv('OUTLOOK_RECIPIENT_EMAIL', '')
        
        if not mailbox_id or not recipient_emails:
            print("[EMAIL] Missing mailbox ID or recipient emails - skipping notification")
            return False
        
        recipients = [email.strip() for email in recipient_emails.split(',') if email.strip()]
        
        if not recipients:
            print("[EMAIL] No valid recipient emails found - skipping notification")
            return False
        
        access_token = get_access_token()
        print(f"[EMAIL] Successfully obtained access token")
        
        base_url = get_app_url()
        print(f"[EMAIL] Using base URL: {base_url}")
        
        html_content = build_html_email(validation_id, base_url)
        
        send_url = f"https://graph.microsoft.com/v1.0/users/{mailbox_id}/sendMail"
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        email_message = {
            'message': {
                'subject': f'IPO Validation Results - {validation_id}',
                'body': {
                    'contentType': 'HTML',
                    'content': html_content
                },
                'toRecipients': [
                    {'emailAddress': {'address': email}} for email in recipients
                ]
            }
        }
        
        response = requests.post(send_url, headers=headers, json=email_message)
        response.raise_for_status()
        
        print(f"[EMAIL] ✓ Successfully sent notification to {len(recipients)} recipient(s): {', '.join(recipients)}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"[EMAIL] ✗ Failed to send notification: {e}")
        if hasattr(e.response, 'text'):
            print(f"[EMAIL] Response: {e.response.text}")
        return False
    except Exception as e:
        print(f"[EMAIL] ✗ Unexpected error sending notification: {e}")
        return False

