import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('MYSQL_HOST', 'localhost')
os.environ.setdefault('MYSQL_USER', 'root')
os.environ.setdefault('MYSQL_PASSWORD', 'REPLACE_ME')
os.environ.setdefault('MYSQL_DB', 'devops')

from app import app as flask_app
from flask_limiter import Limiter

@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    flask_app.config['RATELIMIT_ENABLED'] = False
    with flask_app.test_client() as c:
        yield c

def test_health(client):
    r = client.get('/api/health')
    assert r.status_code == 200
    data = r.get_json()
    assert data['status'] == 'ok'

def test_post_empty_message(client):
    r = client.post(
        '/api/messages',
        json={'message': ''},
        content_type='application/json'
    )
    assert r.status_code == 400

def test_post_too_long_message(client):
    r = client.post(
        '/api/messages',
        json={'message': 'x' * 501},
        content_type='application/json'
    )
    assert r.status_code == 400

def test_pods_endpoint(client):
    r = client.get('/api/pods')
    assert r.status_code == 200
    data = r.get_json()
    assert 'pods' in data
    assert 'source' in data