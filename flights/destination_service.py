from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import threading
import time
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from prometheus_client import Counter

app = Flask(__name__)
requests_counter = Counter('requests_total', 'Total number of requests.')
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///destinations.db'
db = SQLAlchemy(app)

MAX_CONCURRENT_TASKS = 3
concurrent_tasks_semaphore = threading.Semaphore(MAX_CONCURRENT_TASKS)

class Destination(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

TIMEOUT_SECONDS = 5

def perform_with_timeout(func, *args, **kwargs):
    result = None
    exception = None

    def worker():
        nonlocal result, exception
        try:
            with concurrent_tasks_semaphore:
                with app.app_context():
                    result = func(*args, **kwargs)
        except Exception as e:
            exception = e

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=TIMEOUT_SECONDS)

    if thread.is_alive():
        thread.join()
        raise TimeoutError(f'Task timed out after {TIMEOUT_SECONDS} seconds')

    if exception:
        raise exception

    return result

@app.route('/destinations', methods=['GET', 'POST'])
def destinations():
    requests_counter.inc()
    if request.method == 'GET':
        destinations_list = perform_with_timeout(get_all_destinations)
        destinations = [{'id': destination.id, 'name': destination.name} for destination in destinations_list]
        return jsonify(destinations)
    elif request.method == 'POST':
        data = request.get_json()
        perform_with_timeout(create_destination, data['name'])
        return jsonify({'message': 'Destination created successfully'})

def get_all_destinations():
    return Destination.query.all()

def create_destination(name):
    new_destination = Destination(name=name)
    db.session.add(new_destination)
    db.session.commit()

@app.route('/health', methods=['GET'])
def health_check():
    check_results = {
        'database_connection': check_database_connection(),
        'task_timeout': check_task_timeout()
    }

    if all(check_results.values()):
        return jsonify({'status': 'ok', 'checks': check_results})
    else:
        return jsonify({'status': 'bad', 'checks': check_results})

def check_database_connection():
    try:
        with app.app_context():
            engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
            with engine.connect():
                return 'Connected to the database.'
    except OperationalError:
        return False

def check_task_timeout():
    try:
        with app.app_context():
            perform_with_timeout(sleep_function, TIMEOUT_SECONDS + 2)
        return False
    except TimeoutError:
        return 'Task timeouts function as intended.'

def sleep_function(seconds):
    time.sleep(seconds)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5006)