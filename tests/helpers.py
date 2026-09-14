def setup_admin(client):
    st=client.get('/api/setup/status').json()
    if st['needs_setup']:
        r=client.post('/api/setup/first-admin',json={'username':'admin','display_name':'Admin Test','password':'StrongPass123!'})
        assert r.status_code==200, r.text
    r=client.post('/api/auth/login',json={'username':'admin','password':'StrongPass123!'})
    assert r.status_code==200, r.text
