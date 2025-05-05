from flask import Flask, render_template, request, send_file, jsonify
import os
import fitz  # PyMuPDF
from zipfile import ZipFile
import uuid
import shutil
import threading
import time

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ZIP_FOLDER = 'zips'
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB

# folders exist checking
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(ZIP_FOLDER, exist_ok=True)


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        try:
            if 'pdf' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400

            file = request.files['pdf']
            output_format = request.form.get('format', 'png')

            if output_format not in ['png', 'jpeg']:
                return jsonify({'error': 'Unsupported format selected'}), 400

            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            if not file.filename.lower().endswith('.pdf'):
                return jsonify({'error': 'Only PDF files are allowed.'}), 400

            # Saving uploaded PDF
            file_id = str(uuid.uuid4())
            pdf_path = os.path.join(UPLOAD_FOLDER, file_id + '.pdf')
            file.save(pdf_path)

            # Create output folder
            images_folder = os.path.join(OUTPUT_FOLDER, file_id)
            os.makedirs(images_folder, exist_ok=True)

            # Convert PDF to images
            pdf_document = fitz.open(pdf_path)
            for page_number in range(len(pdf_document)):
                page = pdf_document.load_page(page_number)
                pix = page.get_pixmap(matrix=fitz.Matrix(6, 6))
                ext = 'jpg' if output_format == 'jpeg' else 'png'
                image_path = os.path.join(images_folder,
                                          f'page_{page_number + 1}.{ext}')
                pix.save(image_path)
            pdf_document.close()

            # Zip images
            zip_path = os.path.join(ZIP_FOLDER, f"{file_id}.zip")
            with ZipFile(zip_path, 'w') as zipf:
                for root, _, files in os.walk(images_folder):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, images_folder)
                        zipf.write(file_path, arcname)

            return jsonify({'download_link': f"/download/{file_id}"}), 200

        except Exception as e:
            return jsonify({'error': f'Failed to process PDF: {str(e)}'}), 500

    return render_template('upload.html')


@app.route('/download/<file_id>')
def download_zip(file_id):
    zip_path = os.path.join(ZIP_FOLDER, f"{file_id}.zip")
    if not os.path.exists(zip_path):
        return "File not found", 404
    return send_file(zip_path, as_attachment=True)


@app.route('/status')
def status():
    return jsonify({'status': 'ok'}), 200


def cleaner():
    while True:
        folders = [UPLOAD_FOLDER, OUTPUT_FOLDER, ZIP_FOLDER]
        now = time.time()
        for folder in folders:
            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                if os.path.isfile(filepath):
                    if now - os.path.getmtime(filepath) > 2 * 60:
                        os.remove(filepath)
                elif os.path.isdir(filepath):
                    if now - os.path.getmtime(filepath) > 2 * 60:
                        shutil.rmtree(filepath)
        time.sleep(120)


threading.Thread(target=cleaner, daemon=True).start()

#if __name__ == '__main__':
#    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
