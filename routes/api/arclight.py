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
    
    # Debug info
    content_length = request.content_length
    content_type = request.content_type
    debug_msg = f"📁 [V3] Attempting to save Arclight video: {filename} (Size: {content_length}, Type: {content_type})"
    print(f"[ARCLIGHT] {debug_msg}", flush=True)
    current_app.logger.info(debug_msg)

    # If Content-Length is explicitly 0, we can abort early
    if content_length == 0:
        err_msg = f"⚠️ [V3] Arclight upload rejected: Content-Length is 0 for {filename}"
        print(f"[ARCLIGHT] {err_msg}", flush=True)
        current_app.logger.warning(err_msg)
        return "Empty body (Content-Length is 0)", 400
    
    try:
        # Ensure directory exists
        os.makedirs(upload_dir, exist_ok=True)
        
        bytes_written = 0
        
        # 1. Check if it's a multipart/form-data upload (standard file field)
        video_file = request.files.get("video")
        if video_file:
            print(f"[ARCLIGHT] 📦 [V3] Detected as multipart/form-data for {filename}", flush=True)
            current_app.logger.info(f"📦 Arclight upload detected as multipart/form-data for {filename}")
            video_file.save(save_path)
            # Get size of the saved file
            bytes_written = os.path.getsize(save_path)
        else:
            # 2. Otherwise treat it as a raw body upload (streaming)
            print(f"[ARCLIGHT] 🌊 [V3] Detected as raw body streaming for {filename}", flush=True)
            current_app.logger.info(f"🌊 Arclight upload detected as raw body streaming for {filename}")
            with open(save_path, 'wb') as f:
                chunk_size = 1024 * 1024  # 1MB chunks
                while True:
                    chunk = request.stream.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_written += len(chunk)
                
        if bytes_written == 0:
            if os.path.exists(save_path):
                os.remove(save_path)
            warn_msg = f"⚠️ [V3] Arclight upload failed: 0 bytes received for {filename}."
            print(f"[ARCLIGHT] {warn_msg}", flush=True)
            current_app.logger.warning(warn_msg)
            return "No data received (Request body was empty)", 400
        
        success_msg = f"✅ [V3] Arclight video uploaded: {filename} ({bytes_written} bytes saved) to {save_path}"
        print(f"[ARCLIGHT] {success_msg}", flush=True)
        current_app.logger.info(success_msg)
        return "OK", 200
    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        err_msg = f"❌ [V3] Arclight upload error for {filename}: {e}"
        print(f"[ARCLIGHT] {err_msg}", flush=True)
        current_app.logger.error(err_msg)
        return f"Internal Server Error: {str(e)}", 500
