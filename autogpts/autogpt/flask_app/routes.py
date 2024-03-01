from flask import render_template, jsonify, Blueprint, current_app,  stream_with_context, Response, send_from_directory, abort, after_this_request
import json
from time import sleep
import os
from flask import current_app, jsonify
from werkzeug.utils import secure_filename

from utils import redis, Flask_form
from services import tasks
# from utils.formatter import format_doc, read_docx

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('index.html')



@bp.route('/task-status/<task_id>', methods=['GET'])
def task_status(task_id):
    current_app.logger.info("Getting tasks status for task " + task_id)
    def generate(task_id):
        # Simulate getting task status
        task = tasks.split_and_process.AsyncResult(task_id)
        while task.state not in ['SUCCESS', 'FAILURE']:
            sleep(1)
            task = tasks.split_and_process.AsyncResult(task_id)
            if task.state == 'PENDING':
                yield f"data: {json.dumps({'state': task.state, 'status': 'Pending...'})}\n\n"
            elif task.state != 'FAILURE':
                progress = {'state': task.state, 'current': task.info.get('current', 0), 'total': task.info.get('total', 1), 'status': task.info.get('status', '')}
                if 'result' in task.info:
                    progress['result'] = task.info['result']
                yield f"data: {json.dumps(progress)}\n\n"
            else:
                # Handle task failure
                yield f"data: {json.dumps({'state': task.state, 'status': str(task.info)})}\n\n"
                break
            sleep(5)

        # Once task is complete
        yield f"data: {json.dumps({'state': 'SUCCESS', 'status': 'Task completed'})}\n\n"

    return Response(stream_with_context(generate(task_id)), content_type='text/event-stream')


@bp.route('/upload', methods=['POST'])
def index_file():
    current_app.logger.info("About to start processing file...")
    form = Flask_form.UploadForm()

    if form.validate_on_submit():
        file_storage = form.data.data
        model = form.model.data

        if file_storage.filename == '':
            return jsonify({"error": "No selected file"}), 400

        filename = secure_filename(file_storage.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file_storage.save(file_path)

        current_app.logger.info(f"Model is: {model} and file path is: {file_path}")

        task = tasks.split_and_process.delay(file_path, model)
        redis.save(f"file-{task.id}", filename)
        return jsonify({"message": "Task started", "task_id": str(task.id)}), 202
    else:
        return jsonify({"error": "Error scheduling task for processing"}), 400



@bp.route('/download/<task_id>', methods=['GET'])
def download_processed_file(task_id):
    current_app.logger.info("About to download processed file...")
    directory = current_app.config['UPLOAD_FOLDER']
    file_name = redis.get(f"file-{task_id}")
    if not file_name:
       file_name = f"API-{task_id}"
    download_filename = f"{file_name}-{task_id[:5]}-Documentation.docx"
    current_app.logger.info(f"Downloading file... {download_filename}")
    file_path = os.path.join(directory, download_filename)
    if not os.path.exists(file_path):
        return jsonify({"error": f"No file exists for task: {task_id}"}), 404


    # @after_this_request
    # def remove_file(response):
    #     current_app.logger.info(f"Removing file: {response}")
    #     try:
    #         os.remove(file_path)
    #         redis.delete_from_cache(f"file-{task_id}")
    #     except Exception as error:
    #         current_app.logger.error(f"Error removing the downloaded file: {error}")
    #     return response
    directory = 'docs'
    return send_from_directory(directory, download_filename, as_attachment=True)





from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from docx import Document
import os

app = Flask(__name__)

@bp.route('/upload-file', methods=['POST'])
def upload_file():
    current_app.logger.info("Uploading file for formatting")
    if 'document' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['document']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        text = read_docx(filepath)
        formatted_content = format_doc(filepath, text)
        return jsonify({"content": formatted_content})
    else:
        return jsonify({"error": "Invalid file type"}), 400

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ['docx']






