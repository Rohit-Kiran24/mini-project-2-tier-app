import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app as flask_app

@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as c:
        yield c

def test_health(client):
    r = client.get('/api/health')
    assert r.status_code == 200
    assert r.get_json()['status'] == 'ok'

def test_ready_endpoint_exists(client):
    r = client.get('/api/ready')
    assert r.status_code in [200, 503]

def test_post_empty_message(client):
    r = client.post('/api/messages',
                    json={'message': ''},
                    content_type='application/json')
    assert r.status_code == 400

def test_post_too_long_message(client):
    r = client.post('/api/messages',
                    json={'message': 'x' * 501},
                    content_type='application/json')
    assert r.status_code == 400

def test_delete_nonexistent(client):
    r = client.delete('/api/messages/999999')
    assert r.status_code in [404, 500]

def test_get_messages_returns_json(client):
    r = client.get('/api/messages')
    assert r.status_code in [200, 500]
    assert r.content_type == 'application/json'

def test_pods_endpoint(client):
    r = client.get('/api/pods')
    assert r.status_code == 200
    data = r.get_json()
    assert 'pods' in data
