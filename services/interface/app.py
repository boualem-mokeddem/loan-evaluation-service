from flask import Flask, render_template, send_from_directory, jsonify
from flask_cors import CORS
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='.', static_folder='.')
CORS(app)


@app.route('/')
def index():
    logger.info("[Interface] GET /")
    return render_template('index.html')


@app.route('/style.css')
def style():
    return send_from_directory('.', 'style.css', mimetype='text/css')


@app.route('/script.js')
def script():
    return send_from_directory('.', 'script.js', mimetype='application/javascript')


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'Web Interface'}), 200


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint non trouvé', 'status': 'error'}), 404


if __name__ == '__main__':
    logger.info("[Interface] 🚀 Démarrage sur :5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
