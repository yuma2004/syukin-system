from app import User, Shift, Break, db


def test_api_session_is_json(client):
    response = client.get('/api/session')
    payload = response.get_json()

    assert response.status_code == 200
    assert payload['ok'] is True
    data = payload['data']
    assert data['authenticated'] is False
    assert isinstance(data['csrf_token'], str)
    assert data['csrf_token']


def test_api_dashboard_requires_login(client):
    response = client.get('/api/dashboard')
    payload = response.get_json()

    assert response.status_code == 401
    assert payload['ok'] is False
    assert payload['error']['message'] == 'login required'


def test_api_login_and_dashboard_flow(client, test_user):
    response = client.get('/api/session')
    token = response.get_json()['data']['csrf_token']

    login_response = client.post(
        '/api/login',
        json={
            'username': 'testuser',
            'password': 'testpass123',
            'csrf_token': token,
        },
    )
    payload = login_response.get_json()

    assert login_response.status_code == 200
    assert payload['ok'] is True
    assert payload['data']['username'] == 'testuser'

    dashboard_response = client.get('/api/dashboard')
    dashboard = dashboard_response.get_json()['data']

    assert dashboard_response.status_code == 200
    assert dashboard['user']['username'] == 'testuser'
    assert 'dashboard_now_iso' in dashboard


def test_api_clock_in_clock_out_via_json(client, logged_in_user):
    response = client.post('/api/clock/in', json={'csrf_token': ''})
    assert response.status_code == 200

    shift = Shift.query.filter_by(user_id=logged_in_user.id, clock_out_at=None).first()
    assert shift is not None

    open_break = Break.query.filter_by(shift_id=shift.id, end_at=None).first()
    assert open_break is None

    response = client.post('/api/clock/out', json={'csrf_token': ''})
    assert response.status_code == 200
