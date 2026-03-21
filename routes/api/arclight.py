import os
import datetime
from flask import Blueprint, request, current_app
from werkzeug.utils import secure_filename

api_arclight_bp = Blueprint("api_arclight", __name__)

@api_arclight_bp.route("/arclight/upload_video", methods=["POST"])
def upload_video():
    """
    Endpoint for Arclight to upload videos as raw request body.
    Requires X-Token header for authentication.
    Requires X-Video-Filename header for the original filename.
    """
    secret = current_app.config.get("ARCLIGHT_SECRET")
    if request.headers.get("X-Token") != secret:
        current_app.logger.warning(f"⚠️ Unauthorized Arclight upload attempt from {request.remote_addr}")
        return "Unauthorized", 401
    
    # Get filename from header
    original_filename = request.headers.get("X-Video-Filename")
    if not original_filename:
        current_app.logger.warning("⚠️ Arclight upload attempt with missing X-Video-Filename header")
        return "Missing X-Video-Filename header", 400
        
    original_filename = secure_filename(original_filename)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{original_filename}"
    
    upload_dir = current_app.config.get("ARCLIGHT_UPLOAD_DIR")
    save_path = os.path.join(upload_dir, filename)
    
    try:
        # Stream the raw request body to a file to handle large uploads efficiently
        with open(save_path, 'wb') as f:
            # We use request.stream as it's a file-like object for the raw input stream
            # We read in chunks to avoid loading large files into memory
            chunk_size = 1024 * 1024  # 1MB chunks
            while True:
                chunk = request.stream.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                
        current_app.logger.info(f"✅ Arclight video uploaded (raw body): {filename}")
        return "OK", 200
    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        current_app.logger.error(f"❌ Arclight upload error (raw body): {e}")
        return f"Internal Server Error: {str(e)}", 500
