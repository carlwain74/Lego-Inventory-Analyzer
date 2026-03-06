import io
import os
import re
import logging
import tempfile
import configparser
from flask import Flask, render_template, request, jsonify, send_file

# Import the sheet_handler from the generate_sheets module
from generate_sheets import sheet_handler, test_config

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max upload
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0


def capture_output(fn, *args, **kwargs):
    """
    Call fn(*args, **kwargs) and capture all logging output.
    Attaches a temporary StreamHandler to the root logger so that
    any logger.info/warning/error calls inside sheet_handler (or
    any module it imports) are written into a StringIO buffer.
    """
    buf = io.StringIO()

    # Clean format - just the message text, no timestamps or level prefix
    handler = logging.StreamHandler(buf)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter('%(message)s'))

    root_logger = logging.getLogger()
    original_level = root_logger.level
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    try:
        fn(*args, **kwargs)
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(original_level)
        handler.close()

    return buf.getvalue()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate():
    mode = request.form.get('mode')  # 'set' or 'file'
    error = None
    output = ''

    try:
        if mode == 'set':
            set_number = request.form.get('set_number', '').strip()

            if not set_number:
                return jsonify({'error': 'Please enter a set number.'}), 400

            if not re.match(r'^\d+-\d+$', set_number):
                return jsonify({'error': 'Invalid set number format. Use XXXXX-1 (e.g. 75192-1)'}), 400

            output = capture_output(sheet_handler, set_num=set_number, set_list=None, multi_sheet=False,
                                       output_file=os.path.join(OUTPUT_DIR, 'Sets.xlsx'),
                                       config_file=CONFIG_PATH)

        elif mode == 'file':
            uploaded_file = request.files.get('set_file')
            multi_sheet = request.form.get('multi_sheet') == 'true'

            if not uploaded_file or uploaded_file.filename == '':
                return jsonify({'error': 'Please upload a set list file.'}), 400

            # Save uploaded file to a temp location
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as tmp:
                tmp_path = tmp.name
                uploaded_file.save(tmp)

            try:
                output = capture_output(sheet_handler, set_num=None, set_list=tmp_path, multi_sheet=multi_sheet,
                                       output_file=os.path.join(OUTPUT_DIR, 'Sets.xlsx'),
                                       config_file=CONFIG_PATH)
            finally:
                os.unlink(tmp_path)

        else:
            return jsonify({'error': 'Invalid mode selected.'}), 400

    except Exception as e:
        error = str(e)

    if error:
        return jsonify({'error': error, 'output': output})

    return jsonify({'output': output or '(No output returned)'})



CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.ini')

# Output directory — defaults to the project root but can be overridden
# via the OUTPUT_DIR env var (used by Docker to write into the mounted volume)
OUTPUT_DIR = os.environ.get('OUTPUT_DIR', os.path.dirname(__file__))
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.route('/settings', methods=['GET'])
def get_settings():
    """Return only whether each key has a saved value — never the value itself."""
    config = configparser.ConfigParser()
    result = {k: False for k in ('consumer_key', 'consumer_secret', 'token_value', 'token_secret')}
    if os.path.exists(CONFIG_PATH):
        config.read(CONFIG_PATH)
        if 'secrets' in config:
            for key in result:
                result[key] = bool(config['secrets'].get(key, '').strip())
    return jsonify(result)



@app.route('/settings/test', methods=['POST'])
def test_connection():
    """
    Write submitted credentials to a temporary config, run test_config(),
    then unconditionally restore the original config file.
    No backup files are left on disk after this call.
    """
    data = request.get_json() or {}
    allowed = ('consumer_key', 'consumer_secret', 'token_value', 'token_secret')

    # Read original config (may not exist yet)
    original_content = None
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            original_content = f.read()

    try:
        # Build a merged config: start from existing values, overlay submitted ones
        config = configparser.ConfigParser()
        if original_content:
            config.read_string(original_content)
        if 'secrets' not in config:
            config['secrets'] = {}

        for key in allowed:
            val = data.get(key, '').strip()
            if val:
                config['secrets'][key] = val

        # Write temporary test config
        with open(CONFIG_PATH, 'w') as f:
            config.write(f)

        # Run the test
        result = test_config()
        return jsonify({'ok': bool(result)})

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

    finally:
        # Always restore — write back original or remove file if it didn't exist
        if original_content is not None:
            with open(CONFIG_PATH, 'w') as f:
                f.write(original_content)
        elif os.path.exists(CONFIG_PATH):
            os.remove(CONFIG_PATH)

@app.route('/settings', methods=['POST'])
def save_settings():
    """Write any non-empty submitted credentials to config.ini in cleartext."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data received'}), 400

    allowed = ('consumer_key', 'consumer_secret', 'token_value', 'token_secret')
    config = configparser.ConfigParser()

    # Preserve any existing values / other sections
    if os.path.exists(CONFIG_PATH):
        config.read(CONFIG_PATH)

    if 'secrets' not in config:
        config['secrets'] = {}

    for key in allowed:
        val = data.get(key, '').strip()
        if val:  # Only update fields where the user typed something
            config['secrets'][key] = val

    with open(CONFIG_PATH, 'w') as f:
        config.write(f)

    return jsonify({'ok': True})

@app.route('/download')
def download():
    """Serve the generated output file for download.
    sheet_handler writes to Sets.xlsx in the working directory by default."""
    output_path = os.path.join(OUTPUT_DIR, 'Sets.xlsx')
    if not os.path.exists(output_path):
        return jsonify({'error': 'Output file not found. Generate a sheet first.'}), 404
    return send_file(
        output_path,
        as_attachment=True,
        download_name='Sets.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)