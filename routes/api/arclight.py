import os
import datetime
from flask import Blueprint, request, current_app
from werkzeug.utils import secure_filename

api_arclight_bp = Blueprint("api_arclight", __name__)

@api_arclight_bp.route("/arclight/upload_video", methods=["POST"])
def upload_video():
    """
    Endpoint for Arclight to upload videos.
    Requires X-Token header for authentication.
    """
    secret = current_app.config.get("ARCLIGHT_SECRET")
    if request.headers.get("X-Token") != secret:
        current_app.logger.warning(f"⚠️ Unauthorized Arclight upload attempt from {request.remote_addr}")
        return "Unauthorized", 401
    
    video_file = request.files.get("video")
    if not video_file:
        return "No file", 400
    
    # Secure the filename and add a timestamp
    original_filename = secure_filename(video_file.filename)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{original_filename}"
    
    upload_dir = current_app.config.get("ARCLIGHT_UPLOAD_DIR")
    save_path = os.path.join(upload_dir, filename)
    
    try:
        video_file.save(save_path)
        current_app.logger.info(f"✅ Arclight video uploaded: {filename}")
        return "OK", 200
    except Exception as e:
        current_app.logger.error(f"❌ Arclight upload error: {e}")
        return f"Internal Server Error: {str(e)}", 500
