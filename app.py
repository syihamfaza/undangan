import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template
from flask_socketio import SocketIO
from check_stock import run_checker
from map import run_map

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")
process_control = {'stop_requested': False}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('start')
def handle_start(data):
    global process_control
    process_control['stop_requested'] = False
    sheet_index = data.get('sheet_index', 4)

    def background_task():
        socketio.emit('checker_log', "🚀 Proses pengecekan stok dimulai...")
        logs = run_checker(socketio, sheet_index=sheet_index, control=process_control)
        for line in logs:
            socketio.emit('checker_log', line)
        socketio.emit('checker_log', "✅ Proses pengecekan stok selesai.")
        socketio.emit('checker_done')

    socketio.start_background_task(background_task)

@socketio.on('map')
def handle_map(data):
    global process_control
    process_control['stop_requested'] = False
    sheet_index = data.get('sheet_index', 5)

    def background_task():
        socketio.emit('map_log', "🚀 Proses MAP dimulai...")
        logs = run_map(socketio, sheet_index=sheet_index, control=process_control)
        for line in logs:
            socketio.emit('map_log', line)
        socketio.emit('map_log', "✅ Proses MAP selesai.")
        socketio.emit('map_done')

    socketio.start_background_task(background_task)

@socketio.on('stop')
def handle_stop():
    global process_control
    process_control['stop_requested'] = True
    socketio.emit('map_log', "🛑 Proses dihentikan.")  # bisa broadcast ke semua log juga

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5001)
