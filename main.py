"""ThesisMiner v7.0 应用入口

基于 FastAPI 构建的学术论题生成系统。
启动时初始化数据库，注册 API 路由，挂载前端静态资源。
"""
import os
import sys
import threading
import webbrowser
from contextlib import asynccontextmanager

# 确保当前目录在 sys.path 中，以便 backend 包可被导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import database
from backend.routes import config as config_router
from backend.routes import lineage as lineage_router
from backend.routes import creativity as creativity_router
from backend.routes import proposals as proposals_router
from backend.routes import constraints as constraints_router
from backend.routes import sessions as sessions_router
from backend.routes import budgets as budgets_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化数据库，可选自动打开浏览器。"""
    # 初始化数据库
    database.init_db()

    # 自动打开浏览器
    from backend.config import get_settings

    settings = get_settings()
    if settings.auto_open_browser:
        # 延迟 1 秒打开浏览器，确保端口已就绪
        def _open_browser():
            import time

            time.sleep(1)
            webbrowser.open("http://127.0.0.1:8000")

        threading.Thread(target=_open_browser, daemon=True).start()

    yield  # 应用运行期间

    # 关闭时的清理逻辑（如有）
    pass


app = FastAPI(
    title="ThesisMiner v7.0",
    version="7.0.0",
    lifespan=lifespan,
)

# 配置 CORS：开发环境允许所有源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 注册 API 路由（路由内部已定义 prefix）
app.include_router(config_router.router)
app.include_router(lineage_router.router)
app.include_router(creativity_router.router)
app.include_router(proposals_router.router)
app.include_router(constraints_router.router)
app.include_router(sessions_router.router)
app.include_router(budgets_router.router)


# 挂载前端静态文件目录到根路径
# 仅当 frontend 目录存在时挂载，避免在未构建前端时启动失败
_frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
