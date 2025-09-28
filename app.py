"""
Flask app for removing image backgrounds using `rembg`.

Updates:
- Deletes uploads after processing result
- Added <aside> section in templates for showing ads (monetization placeholder)
"""

from flask import Flask, request, send_file, redirect, url_for, flash, render_template_string
from werkzeug.utils import secure_filename
from rembg import remove
from PIL import Image
import io
import os
import uuid
import base64

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
RESULTS_FOLDER = os.path.join(os.path.dirname(__file__), 'results')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff'}
MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB upload limit

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULTS_FOLDER'] = RESULTS_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.secret_key = 'dev-secret-key-change-this'

INDEX_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Background Remover</title>
    <style>
      body { font-family: Arial, sans-serif; background:#f6f6f6; color:#222; }
      .container { max-width:1100px; margin:40px auto; padding:20px; background:white; border-radius:8px; box-shadow:0 6px 18px rgba(0,0,0,0.08); display:flex; gap:20px; }
      .content { flex:3 }
      aside { flex:1; background:#fafafa; border-left:1px solid #ddd; padding:12px; border-radius:6px; }
      h1 { margin-top:0 }
      .uploads { margin-top:12px }
      .btn { display:inline-block; padding:10px 14px; border-radius:6px; background:#0066ff; color:white; text-decoration:none; }
      .hint { color:#666; font-size:0.9rem }
    </style>
  </head>
  <body>
    <div class="container">
      <div class="content">
        <h1>Remove Image Background</h1>
        {% with messages = get_flashed_messages() %}
          {% if messages %}
            <ul>
              {% for msg in messages %}
                <li style="color:crimson">{{msg}}</li>
              {% endfor %}
            </ul>
          {% endif %}
        {% endwith %}

        <form method="post" action="{{ url_for('remove_bg') }}" enctype="multipart/form-data">
          <label for="file">Choose image (PNG/JPG/WEBP/TIFF/BMP)</label><br>
          <input type="file" id="file" name="file" accept="image/*" required>
          <div class="uploads">
            <button class="btn" type="submit">Remove Background</button>
          </div>
        </form>

        <div class="hint">
          <p>Notes: Works with most objects. Max upload: 25 MB. Output is a transparent PNG.</p>
        </div>
      </div>
      <aside>
        <h3>Advertisement</h3>
        <p>Place your ad code here (Google AdSense / Banner / Affiliate links).</p>
      </aside>
    </div>
  </body>
</html>
"""

RESULT_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Result — Background Removed</title>
    <style>
      body { font-family: Arial, sans-serif; background:#f6f6f6; color:#222; }
      .container { max-width:1100px; margin:40px auto; padding:20px; background:white; border-radius:8px; box-shadow:0 6px 18px rgba(0,0,0,0.08); display:flex; gap:20px; }
      .content { flex:3 }
      aside { flex:1; background:#fafafa; border-left:1px solid #ddd; padding:12px; border-radius:6px; }
      .preview { display:flex; gap:24px; flex-wrap:wrap; }
      .preview img { max-width:360px; max-height:360px; border:1px solid #ddd; border-radius:6px; }
      .btn { display:inline-block; padding:10px 14px; border-radius:6px; background:#0066ff; color:white; text-decoration:none; }
      .meta { color:#666 }
    </style>
  </head>
  <body>
    <div class="container">
      <div class="content">
        <h1>Background Removed</h1>
        <div class="preview">
          <div>
            <strong>Original</strong><br>
            <img src="data:image/{{ orig_ext }};base64,{{ orig_b64 }}" alt="original">
          </div>
          <div>
            <strong>Result (PNG, transparent)</strong><br>
            <img src="data:image/png;base64,{{ result_b64 }}" alt="result">
          </div>
        </div>
        <div style="margin-top:12px">
          <a class="btn" href="{{ url_for('download_result', filename=result_filename) }}">Download PNG</a>
          <a style="margin-left:12px; color:#333; text-decoration:none;" href="{{ url_for('index') }}">Process another image</a>
        </div>
        <p class="meta">Filename: {{ result_filename }} | Size: {{ result_size_kb }} KB</p>
      </div>
      <aside>
        <h3>Advertisement</h3>
        <p>Place your ad code here (Google AdSense / Banner / Affiliate links).</p>
      </aside>
    </div>
  </body>
</html>
"""

# Helpers
def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/', methods=['GET'])
def index():
    return render_template_string(INDEX_HTML)


@app.route('/remove', methods=['POST'])
def remove_bg():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))

    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('index'))

    if not allowed_file(file.filename):
        flash('File type not allowed.')
        return redirect(url_for('index'))

    orig_name = secure_filename(file.filename)
    ext = orig_name.rsplit('.', 1)[1].lower()
    unique_id = uuid.uuid4().hex
    orig_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_orig.{ext}")
    file.save(orig_path)

    try:
        with Image.open(orig_path) as img:
            img = img.convert('RGBA')
            input_bytes = io.BytesIO()
            img.save(input_bytes, format='PNG')
            input_bytes.seek(0)
            result_bytes = remove(input_bytes.read())

            result_filename = f"{unique_id}_result.png"
            result_path = os.path.join(app.config['RESULTS_FOLDER'], result_filename)
            with open(result_path, 'wb') as f:
                f.write(result_bytes)

            with open(result_path, 'rb') as f:
                result_b64 = base64.b64encode(f.read()).decode('ascii')

            with open(orig_path, 'rb') as f:
                orig_b64 = base64.b64encode(f.read()).decode('ascii')

            result_size_kb = round(os.path.getsize(result_path) / 1024, 1)

            # Delete the original upload after processing
            if os.path.exists(orig_path):
                os.remove(orig_path)

            return render_template_string(RESULT_HTML,
                                          orig_b64=orig_b64,
                                          result_b64=result_b64,
                                          orig_ext=ext,
                                          result_filename=result_filename,
                                          result_size_kb=result_size_kb)

    except Exception as e:
        app.logger.exception('Processing failed')
        flash('Failed to process image: ' + str(e))
        if os.path.exists(orig_path):
            os.remove(orig_path)
        return redirect(url_for('index'))


@app.route('/download/<path:filename>', methods=['GET'])
def download_result(filename):
    safe = secure_filename(filename)
    path = os.path.join(app.config['RESULTS_FOLDER'], safe)
    if not os.path.exists(path):
        flash('File not found')
        return redirect(url_for('index'))
    return send_file(path, as_attachment=True, download_name=safe)


if __name__ == '__main__':
    app.run(debug=False, port=80)
