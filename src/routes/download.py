from flask import Blueprint, request, jsonify, send_file
from flask_cors import CORS
import requests
import re
import os
import tempfile
import asyncio
from playwright.async_api import async_playwright
import logging

download_bp = Blueprint("download", __name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_pinterest_data_playwright(pin_url):
    """Get Pinterest pin data using Playwright for better reliability"""
    try:
        # Extract pin ID from URL
        pin_id_match = re.search(r"/pin/(\\d+)", pin_url)
        if not pin_id_match:
            raise ValueError("Invalid Pinterest URL format")
        
        pin_id = pin_id_match.group(1)
        logger.info(f"Extracting data for pin ID: {pin_id}")
        
        # Use a realistic user agent
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        
        async with async_playwright() as p:
            # Launch browser with stealth settings
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--no-first-run",
                    "--no-zygote",
                    "--disable-gpu"
                ]
            )
            
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={
                    "width": 1920,
                    "height": 1080
                },
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                }
             )
            
            page = await context.new_page()
            
            # Navigate to the pin URL
            logger.info(f"Navigating to: {pin_url}")
            response = await page.goto(pin_url, wait_until="networkidle", timeout=30000)
            
            if response.status != 200:
                raise Exception(f"Failed to load page, status: {response.status}")
            
            # Wait for content to load
            await asyncio.sleep(3)
            
            # Try to find video first
            video_element = await page.query_selector("video")
            if video_element:
                video_src = await video_element.get_attribute("src")
                if video_src:
                    logger.info(f"Found video: {video_src}")
                    await browser.close()
                    return {
                        "type": "video",
                        "url": video_src,
                        "title": "Pinterest Video",
                        "thumbnail": None
                    }
            
            # If no video, look for image
            img_selectors = [
                "img[data-test-id=\"pin-image\"]",
                "img[alt*=\"Pin\"]",
                "img[src*=\"pinimg.com\"]",
                "div[data-test-id=\"visual-content-container\"] img"
            ]
            
            for selector in img_selectors:
                img_element = await page.query_selector(selector)
                if img_element:
                    img_src = await img_element.get_attribute("src")
                    if img_src and "pinimg.com" in img_src:
                        # Convert to higher resolution if possible
                        high_res_url = img_src.replace("/236x/", "/originals/").replace("/474x/", "/originals/")
                        logger.info(f"Found image: {high_res_url}")
                        await browser.close()
                        return {
                            "type": "image",
                            "url": high_res_url,
                            "title": "Pinterest Image",
                            "thumbnail": img_src
                        }
            
            await browser.close()
            raise Exception("No video or image found on the page")
            
    except Exception as e:
        logger.exception("Error in get_pinterest_data_playwright:")
        raise e

async def download_file_content_async(url):
    """Download file content from URL with better headers"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site",
            "Referer": "https://www.pinterest.com/"
        }
        
        logger.info(f"Downloading from: {url}" )
        response = requests.get(url, headers=headers, timeout=30, stream=True)
        
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "application/octet-stream")
            return response.content, content_type
        else:
            raise Exception(f"Failed to download file, status code: {response.status_code}")
            
    except Exception as e:
        logger.exception("Error in download_file_content:")
        raise e

@download_bp.route("/download", methods=["POST"])
def download_content():
    """Download Pinterest content endpoint"""
    try:
        data = request.get_json()
        if not data or "url" not in data:
            return jsonify({"error": "URL is required"}), 400
        
        pin_url = data["url"]
        logger.info(f"Processing download request for: {pin_url}")
        
        # Validate Pinterest URL
        if "pinterest.com" not in pin_url:
            return jsonify({"error": "Invalid Pinterest URL"}), 400
        
        # Get Pinterest data using Playwright
        pin_data = asyncio.run(get_pinterest_data_playwright(pin_url))
        
        if not pin_data:
            return jsonify({"error": "Could not extract content from Pinterest URL"}), 404
        
        # Download the file
        file_content, content_type = asyncio.run(download_file_content_async(pin_data["url"]))
        
        if not file_content:
            return jsonify({"error": "Could not download the file"}), 500
        
        # Determine file extension
        if pin_data["type"] == "video":
            file_extension = ".mp4"
            filename = f"pinterest_video_{pin_data.get("title", "download")[:20]}.mp4"
        else:
            file_extension = ".jpg"
            if "image/png" in content_type:
                file_extension = ".png"
            elif "image/gif" in content_type:
                file_extension = ".gif"
            filename = f"pinterest_image_{pin_data.get("title", "download")[:20]}{file_extension}"
        
        # Clean filename
        filename = re.sub(r"[^\\w\\-_\\.]", "_", filename)
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
        temp_file.write(file_content)
        temp_file.close()
        
        logger.info(f"Successfully processed download: {filename}")
        
        return send_file(
            temp_file.name,
            as_attachment=True,
            download_name=filename,
            mimetype=content_type
        )
        
    except Exception as e:
        logger.exception("Error in download_content:")
        return jsonify({"error": f"Unable to download content: {str(e)}"}), 500

@download_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "Pinterest Downloader API"})
