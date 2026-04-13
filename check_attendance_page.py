import requests
r = requests.get('http://127.0.0.1:8000/attendance/start/')
print('Status', r.status_code)
print('Scan This Class' in r.text)
print('subject-scan-button' in r.text)
print('Scan This Class count:', r.text.count('Scan This Class'))
print('subject-scan-button count:', r.text.count('subject-scan-button'))