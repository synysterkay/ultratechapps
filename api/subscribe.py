#!/usr/bin/env python3
"""
Newsletter Subscription API Handler
Cloudflare Pages Function / Vercel Serverless Function
"""
import json
import os
import requests

def handler(event, context):
    """
    Handle newsletter subscription POST requests
    Can be deployed to Cloudflare Pages Functions or Vercel
    """
    
    # CORS headers
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Content-Type': 'application/json'
    }
    
    # Handle OPTIONS request (CORS preflight)
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': ''
        }
    
    # Only accept POST requests
    if event.get('httpMethod') != 'POST':
        return {
            'statusCode': 405,
            'headers': headers,
            'body': json.dumps({'error': 'Method not allowed'})
        }
    
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        email = body.get('email', '').strip()
        
        if not email or '@' not in email:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Invalid email address'})
            }
        
        # Add to Mailgun mailing list
        api_key = os.environ.get('MAILGUN_API_KEY')
        domain = os.environ.get('MAILGUN_DOMAIN', 'sandboxa4301ed5a4be45c78f5a6d53c6f1452b.mailgun.org')
        mailing_list = f'subscribers@{domain}'
        
        url = f'https://api.mailgun.net/v3/lists/{mailing_list}/members'
        
        response = requests.post(
            url,
            auth=('api', api_key),
            data={
                'address': email,
                'subscribed': 'yes',
                'upsert': 'yes',
                'vars': json.dumps({
                    'source': 'bestaiapps.site',
                    'subscribed_at': context.get('timestamp', '')
                })
            }
        )
        
        if response.status_code == 200:
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'success': True,
                    'message': 'Successfully subscribed!'
                })
            }
        else:
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Failed to subscribe. Please try again.'
                })
            }
            
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }

# For local testing
if __name__ == '__main__':
    test_event = {
        'httpMethod': 'POST',
        'body': json.dumps({'email': 'test@example.com'})
    }
    result = handler(test_event, {})
    print(json.dumps(result, indent=2))
