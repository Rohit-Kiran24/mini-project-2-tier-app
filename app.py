import os
import time
import threading
import json
import logging
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from flask_talisman import Talisman
from prometheus_flask_exporter import PrometheusMetrics
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

# ── Structured JSON logging ───────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "msg": "%(message)s"}'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per hour"],
)
CORS(app, origins=["http://localhost:5000"])
Talisman(app, force_https=False, content_security_policy=False)
metrics = PrometheusMetrics(app)

# ── Database connection pool ───────────────────────────────────────────
DB_URL = "mysql+pymysql://{user}:{pw}@{host}/{db}".format(
    user=os.environ.get("MYSQL_USER", "root"),
    pw=os.environ.get("MYSQL_PASSWORD", "admin"),
    host=os.environ.get("MYSQL_HOST", "mysql"),
    db=os.environ.get("MYSQL_DB", "mydb"),
)

engine = create_engine(
    DB_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)

def wait_for_db(retries=10, delay=2):
    for attempt in range(retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database ready after %d attempts", attempt + 1)
            return True
        except Exception as e:
            logger.warning("DB not ready (attempt %d/%d): %s", attempt + 1, retries, e)
            time.sleep(delay * (2 ** min(attempt, 4)))
    raise RuntimeError("Database unavailable after %d retries" % retries)

def init_db():
    wait_for_db()
    with engine.connect() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message TEXT
            )
        '''))
        conn.commit()

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

def _get_pods_data():
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
            return {"pods": result, "source": "live"}
        except Exception:
            pass
    return {
        "source": "simulated",
        "pods": [
            {"name": "flaskapp-demo", "status": "running",
             "restarts": 0, "node": "local-docker", "image": "flaskapp:latest"},
            {"name": "mysql-0", "status": "running",
             "restarts": 0, "node": "local-docker", "image": "mysql:5.7"},
        ]
    }

# ── Spike flag ────────────────────────────────────────────────────────
SPIKE_FLAG = "/tmp/spike_active"

# ── Existing routes ───────────────────────────────────────────────────
@app.route('/')
def hello():
    try:
        with engine.connect() as conn:
            rows = conn.execute(text('SELECT message FROM messages')).fetchall()
        messages = rows
    except Exception:
        messages = []
    return render_template('index.html', messages=messages)

@app.route('/submit', methods=['POST'])
def submit():
    new_message = request.form.get('new_message')
    with engine.begin() as conn:
        conn.execute(text('INSERT INTO messages (message) VALUES (:msg)'),
                     {"msg": new_message})
    return jsonify({'message': new_message})

# ── New API routes ────────────────────────────────────────────────────
@app.route("/api/messages", methods=["GET"])
def api_get_messages():
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, message FROM messages ORDER BY id DESC LIMIT 50")
            ).fetchall()
        return jsonify({"status": "ok",
                        "messages": [{"id": r[0], "message": r[1]} for r in rows],
                        "count": len(rows)})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/messages", methods=["POST"])
@limiter.limit("20 per minute")
def api_post_message():
    data = request.get_json()
    text_val = (data or {}).get("message", "").strip()
    if not text_val:
        return jsonify({"status": "error", "error": "Message is empty"}), 400
    if len(text_val) > 500:
        return jsonify({"status": "error", "error": "Message too long"}), 400
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("INSERT INTO messages (message) VALUES (:msg)"),
                {"msg": text_val}
            )
        return jsonify({"status": "ok", "id": result.lastrowid, "message": text_val})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/messages/<int:msg_id>", methods=["DELETE"])
@limiter.limit("20 per minute")
def api_delete_message(msg_id):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM messages WHERE id = :id"),
                {"id": msg_id}
            )
        if result.rowcount == 0:
            return jsonify({"status": "error", "error": "Not found"}), 404
        return jsonify({"status": "ok", "deleted_id": msg_id})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/pods", methods=["GET"])
def api_get_pods():
    data = _get_pods_data()
    return jsonify({"status": "ok", **data})


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
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return jsonify({"status": "ready"})
    except Exception:
        return jsonify({"status": "not ready"}), 503


@app.route("/api/stream")
def api_stream():
    def event_stream():
        while True:
            try:
                pod_data = _get_pods_data()
                with engine.connect() as conn:
                    count = conn.execute(
                        text("SELECT COUNT(*) FROM messages")
                    ).scalar()
                payload = json.dumps({
                    "pods": pod_data["pods"],
                    "source": pod_data["source"],
                    "msg_count": count,
                })
                yield f"data: {payload}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            time.sleep(3)
    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)