import sys
sys.path.append('.')
from app import app

client = app.test_client()
response = client.get('/api/dashboard')
print("Status:", response.status_code)
print("Data:", response.data.decode('utf-8'))
