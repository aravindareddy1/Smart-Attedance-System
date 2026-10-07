from tests.conftest import login_client


def test_analytics_endpoints_authenticated(client):
    login_client(client, 'teacher@test.edu', 'Teacher@123')

    # Summary
    res = client.get('/analytics/api/summary')
    assert res.status_code == 200
    data = res.get_json()
    assert 'total_students' in data
    assert 'avg_attendance_pct' in data

    # Trend
    res = client.get('/analytics/api/trend')
    assert res.status_code == 200
    data = res.get_json()
    assert 'labels' in data
    assert 'percentages' in data

    # Classwise
    res = client.get('/analytics/api/classwise')
    assert res.status_code == 200
    data = res.get_json()
    assert 'labels' in data
    assert 'percentages' in data

    # Subjectwise
    res = client.get('/analytics/api/subjectwise')
    assert res.status_code == 200
    data = res.get_json()
    assert 'labels' in data

    # Heatmap
    res = client.get('/analytics/api/heatmap')
    assert res.status_code == 200
    data = res.get_json()
    assert 'weekdays' in data
    assert 'periods' in data
    assert 'data' in data

    # Top Absent
    res = client.get('/analytics/api/top-absent')
    assert res.status_code == 200
    data = res.get_json()
    assert 'labels' in data
    assert 'counts' in data

    # Distribution
    res = client.get('/analytics/api/distribution')
    assert res.status_code == 200
    data = res.get_json()
    assert 'labels' in data
    assert 'counts' in data
