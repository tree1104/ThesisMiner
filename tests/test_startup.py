"""启动检查脚本"""
import urllib.request
import json

urls = [
    "http://127.0.0.1:8000/api/status",
    "http://127.0.0.1:8000/api/config",
    "http://127.0.0.1:8000/api/proposals",
    "http://127.0.0.1:8000/api/sessions",
    "http://127.0.0.1:8000/api/budgets/summary",
    "http://127.0.0.1:8000/api/lineage",
    "http://127.0.0.1:8000/api/lineage/graph",
    "http://127.0.0.1:8000/api/budgets/ledger",
    "http://127.0.0.1:8000/api/budgets/pricing",
    "http://127.0.0.1:8000/",
    "http://127.0.0.1:8000/scripts/api.js",
    "http://127.0.0.1:8000/scripts/app.js",
    "http://127.0.0.1:8000/scripts/pages/dashboard.js",
    "http://127.0.0.1:8000/styles/main.css",
]

print("启动检查:")
print("-" * 50)
for url in urls:
    path = url.replace("http://127.0.0.1:8000", "")
    try:
        resp = urllib.request.urlopen(url, timeout=5)
        print(f"  {path:35s} -> {resp.status}")
    except Exception as e:
        print(f"  {path:35s} -> ERROR: {e}")
