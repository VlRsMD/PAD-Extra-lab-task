from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import time
import threading
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from prometheus_client import Counter
from datetime import datetime

app = Flask(__name__)
requests_counter = Counter('requests_total', 'Total number of requests.')
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///flights.db'
db = SQLAlchemy(app)

MAX_CONCURRENT_TASKS = 3
concurrent_tasks_semaphore = threading.Semaphore(MAX_CONCURRENT_TASKS)

class Origin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

class Destination(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

class Airline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

class Flight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    flight_number = db.Column(db.String(20), nullable=False)
    origin_id = db.Column(db.Integer, db.ForeignKey('origin.id'))
    destination_id = db.Column(db.Integer, db.ForeignKey('destination.id'))
    airline_id = db.Column(db.Integer, db.ForeignKey('airline.id'))
    departure_time = db.Column(db.DateTime)
    arrival_time = db.Column(db.DateTime)

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

@app.route('/flights', methods=['GET', 'POST'])
def flights():
    requests_counter.inc()
    if request.method == 'GET':
        flights_list = perform_with_timeout(get_all_flights)
        flights = [{'id': flight.id, 'flight_number': flight.flight_number, 'origin_id': flight.origin_id,
                    'destination_id': flight.destination_id, 'airline_id': flight.airline_id,
                    'departure_time': str(flight.departure_time), 'arrival_time': str(flight.arrival_time)}
                   for flight in flights_list]
        return jsonify(flights)
    elif request.method == 'POST':
        data = request.get_json()
        perform_with_timeout(create_flight, data['flight_number'], data['origin_id'], data['destination_id'],
                              data['airline_id'], data['departure_time'], data['arrival_time'])
        return jsonify({'message': 'Flight created successfully'})

def get_all_flights():
    return Flight.query.all()

def create_flight(flight_number, origin_id, destination_id, airline_id, departure_time, arrival_time):
    departure_time_object = datetime.strptime(departure_time, '%Y-%m-%dT%H:%M:%S').date()
    arrival_time_object = datetime.strptime(arrival_time, '%Y-%m-%dT%H:%M:%S').date()

    new_flight = Flight(flight_number=flight_number, origin_id=origin_id, destination_id=destination_id,
                        airline_id=airline_id, departure_time=departure_time_object, arrival_time=arrival_time_object)
    db.session.add(new_flight)
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
    app.run(debug=True, host='0.0.0.0', port=5004)