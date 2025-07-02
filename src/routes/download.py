from flask import Blueprint, request, jsonify, Response
import re
import requests
from urllib.parse import urlparse
import json
import io

download_bp = Blueprint('download', __name__)

def extract_pinterest_id(url):
    """Extract Pinterest pin ID from URL"""
    patterns = [
        r'pinterest\.com/pin/(\d+)',
        r'pin\.it/(\w+)',
        r'pinterest\.com.*?/pin/(\d+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_pinterest_data(pin_id):
    """Get Pinterest pin data"""
    try:
        # Pinterest API endpoint (this is a simplified version)
        # In a real implementation, you'd need proper Pinterest API access
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Try to get pin data from Pinterest
        url = f"https://www.pinterest.com/pin/{pin_id}/"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Extract JSON data from the page
            # This is a simplified extraction - in reality, Pinterest uses complex JS rendering
            content = response.text
            
            # Look for video or image URLs in the page content
            video_patterns = [
                r'"url":"(https://[^"]*\.mp4[^"]*)"',
                r'"video_url":"(https://[^"]*)"',
                r'"url":"(https://v\.pinimg\.com/[^"]*\.mp4[^"]*)"'
            ]
            
            image_patterns = [
                r'"url":"(https://i\.pinimg\.com/[^"]*)"',
                r'"images":\s*{\s*"orig":\s*{\s*"url":\s*"([^"]*)"'
            ]
            
            # Try to find video first
            for pattern in video_patterns:
                match = re.search(pattern, content)
                if match:
                    video_url = match.group(1).replace('\\/', '/')
                    return {
                        'type': 'video',
                        'url': video_url,
                        'title': 'Pinterest Video',
                        'thumbnail': None
                    }
            
            # If no video found, look for images
            for pattern in image_patterns:
                match = re.search(pattern, content)
                if match:
                    image_url = match.group(1).replace('\\/', '/')
                    return {
                        'type': 'image',
                        'url': image_url,
                        'title': 'Pinterest Image',
                        'thumbnail': image_url
                    }
        
        return None
        
    except Exception as e:
        logging.exception("Error in get_pinterest_data:")
        raise e

def download_file_content(url):
    """Download file content from URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30, stream=True)
        if response.status_code == 200:
            return response.content, response.headers.get('content-type', 'application/octet-stream')
        return None, None
    except Exception as e:
        logging.exception("Error in download_file_content:")
        raise e

@download_bp.route('/download', methods=['POST'])
def download_content():
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400
        
        url = data['url'].strip()
        
        # Validate Pinterest URL
        if not any(domain in url.lower() for domain in ['pinterest.com', 'pin.it']):
            return jsonify({'error': 'Please provide a valid Pinterest URL'}), 400
        
        # Extract pin ID
        pin_id = extract_pinterest_id(url)
        if not pin_id:
            return jsonify({'error': 'Could not extract Pinterest pin ID from URL'}), 400
        
        # Get Pinterest content data
        content_data = get_pinterest_data(pin_id)
        if not content_data:
            return jsonify({'error': 'Could not fetch content from Pinterest. The pin might be private or deleted.'}), 404
        
        # Download the actual file content
        file_content, content_type = download_file_content(content_data['url'])
        if not file_content:
            return jsonify({'error': 'Could not download the file content'}), 500
        
        # Determine file extension based on content type
        file_extension = '.jpg'  # default
        if content_data['type'] == 'video':
            file_extension = '.mp4'
        elif 'image/png' in content_type:
            file_extension = '.png'
        elif 'image/gif' in content_type:
            file_extension = '.gif'
        elif 'image/webp' in content_type:
            file_extension = '.webp'
        
        # Create filename
        filename = f"pinterest_{content_data['type']}_{pin_id}{file_extension}"
        
        # Return file as response
        return Response(
            file_content,
            mimetype=content_type,
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': content_type
            }
        )
        
    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@download_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'Pinterest Downloader API'})

