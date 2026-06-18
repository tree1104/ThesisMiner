"""前端资源可访问性检查"""
import urllib.request

urls = [
    "http://127.0.0.1:8000/",
    "http://127.0.0.1:8000/api/status",
    "http://127.0.0.1:8000/scripts/api.js",
    "http://127.0.0.1:8000/scripts/app.js",
    "http://127.0.0.1:8000/scripts/pages/dashboard.js",
    "http://127.0.0.1:8000/scripts/pages/generate.js",
    "http://127.0.0.1:8000/scripts/pages/lineage.js",
    "http://127.0.0.1:8000/scripts/pages/sessions.js",
    "http://127.0.0.1:8000/scripts/pages/budgets.js",
    "http://127.0.0.1:8000/scripts/pages/settings.js",
    "http://127.0.0.1:8000/styles/main.css",
]

print("前端资源可访问性检查:")
print("-" * 50)
all_ok = True
for url in urls:
    path = url.replace("http://127.0.0.1:8000", "")
    try:
        resp = urllib.request.urlopen(url)
        status = resp.status
        print(f"  {path:40s} -> {status}")
        if status != 200:
            all_ok = False
    except Exception as e:
        print(f"  {path:40s} -> ERROR: {e}")
        all_ok = False

print("-" * 50)
print(f"结果: {'全部可访问' if all_ok else '存在不可访问资源'}")
