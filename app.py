import os
import time
import threading
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_mysqldb import MySQL

app = Flask(__name__)

# Configure MySQL from environment variables
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'default_user')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', 'default_password')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB', 'default_db')

# Initialize MySQL
mysql = MySQL(app)

def init_db():
    with app.app_context():
        cur = mysql.connection.cursor()
        cur.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            message TEXT
        );
        ''')
        mysql.connection.commit()
        cur.close()

# ── Existing routes (unchanged) ───────────────────────────────────────
@app.route('/')
def hello():
    cur = mysql.connection.cursor()
    cur.execute('SELECT message FROM messages')
    messages = cur.fetchall()
    cur.close()
    return render_template('index.html', messages=messages)

@app.route('/submit', methods=['POST'])
def submit():
    new_message = request.form.get('new_message')
    cur = mysql.connection.cursor()
    cur.execute('INSERT INTO messages (message) VALUES (%s)', [new_message])
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': new_message})

# ── K8s client helper ─────────────────────────────────────────────────
def get_k8s_client():
    try:
        from kubernetes import client, config
        try:
            config.load_incluster_config()
        except Exception:
            config.load_kube_config()
        return client.CoreV1Api()
    except Exception:
        return None

# ── Spike flag (file-based lock — works across Gunicorn workers) ──────
SPIKE_FLAG = "/tmp/spike_active"

# ── New API routes ────────────────────────────────────────────────────
@app.route("/api/messages", methods=["GET"])
def api_get_messages():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, message FROM messages ORDER BY id DESC LIMIT 50")
        rows = [{"id": r[0], "message": r[1]} for r in cur.fetchall()]
        cur.close()
        return jsonify({"status": "ok", "messages": rows, "count": len(rows)})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/messages", methods=["POST"])
def api_post_message():
    data = request.get_json()
    text = (data or {}).get("message", "").strip()
    if not text:
        return jsonify({"status": "error", "error": "Message is empty"}), 400
    if len(text) > 500:
        return jsonify({"status": "error", "error": "Message too long"}), 400
    try:
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO messages (message) VALUES (%s)", (text,))
        mysql.connection.commit()
        cur.close()
        return jsonify({"status": "ok", "message": text})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/messages/<int:msg_id>", methods=["DELETE"])
def api_delete_message(msg_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM messages WHERE id = %s", (msg_id,))
        mysql.connection.commit()
        affected = cur.rowcount
        cur.close()
        if affected == 0:
            return jsonify({"status": "error", "error": "Not found"}), 404
        return jsonify({"status": "ok", "deleted_id": msg_id})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/pods", methods=["GET"])
def api_get_pods():
    namespace = os.environ.get("POD_NAMESPACE", "default")
    v1 = get_k8s_client()
    if v1:
        try:
            pods = v1.list_namespaced_pod(namespace=namespace)
            result = []
            for p in pods.items:
                containers = p.status.container_statuses or []
                restarts = sum(c.restart_count for c in containers)
                state = "running"
                if p.status.phase == "Pending":
                    state = "pending"
                elif p.status.phase == "Failed":
                    state = "crashed"
                elif not all(c.ready for c in containers):
                    state = "recovering"
                result.append({
                    "name": p.metadata.name,
                    "status": state,
                    "restarts": restarts,
                    "node": p.spec.node_name or "unknown",
                    "image": containers[0].image if containers else "unknown",
                })
            return jsonify({"status": "ok", "pods": result, "source": "live"})
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)}), 500
    else:
        return jsonify({
            "status": "ok",
            "source": "simulated",
            "pods": [
                {"name": "flaskapp-demo", "status": "running",
                 "restarts": 0, "node": "local-docker", "image": "flaskapp:latest"},
                {"name": "mysql-0", "status": "running",
                 "restarts": 0, "node": "local-docker", "image": "mysql:5.7"},
            ]
        })


@app.route("/api/spike", methods=["POST"])
def api_spike():
    if os.path.exists(SPIKE_FLAG):
        return jsonify({"status": "already_running"})
    open(SPIKE_FLAG, "w").close()
    def burn_cpu(duration=10):
        deadline = time.time() + duration
        while time.time() < deadline:
            _ = [x**2 for x in range(10000)]
        try:
            os.remove(SPIKE_FLAG)
        except FileNotFoundError:
            pass
    threading.Thread(target=burn_cpu, daemon=True).start()
    return jsonify({"status": "ok", "message": "Spike started for 10s"})


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/ready", methods=["GET"])
def ready():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT 1")
        cur.close()
        return jsonify({"status": "ready"})
    except Exception:
        return jsonify({"status": "not ready"}), 503


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)