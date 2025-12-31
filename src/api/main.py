from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles  # 用於開發時提供前端靜態檔案
from pathlib import Path
from api.routes.analysis import router as analysis_router
from api.routes.reduce import router as reduce_router

# 建立一個 FastAPI 應用程式，用於處理 CSV 分析相關的 API 請求
app = FastAPI(title="CSV Analysis API")

@app.get("/")
async def root():
    return {"status": "ok"}

# 提供前端介面頁面，回傳 index.html 的內容（保留舊路由以兼容）
@app.get("/ui", response_class=HTMLResponse)
async def serve_frontend():
    frontend_path = Path("src/frontend/index.html")
    if frontend_path.is_file():
        return frontend_path.read_text()
    return "index.html not found."

# Overview UI（暫時沿用 index.html，之後再拆）
@app.get("/overview", response_class=HTMLResponse)
async def serve_overview_ui():
    frontend_path = Path("src/frontend/overview.html")
    if frontend_path.is_file():
        return frontend_path.read_text()
    return "overview.html not found."

@app.get("/reduce", response_class=HTMLResponse)
async def serve_reducer_ui():
    frontend_path = Path("src/frontend/select.html")
    if frontend_path.is_file():
        return frontend_path.read_text()
    return "select.html not found."

# 將 src/frontend 目錄的靜態檔案掛載到路徑 "/static"
# 讓 /static/app.js、/static/style.css 等請求可以直接取得對應檔案
# 請注意：這僅適用於開發用途，並非正式環境的靜態檔案解決方案
app.include_router(analysis_router, prefix="/analysis")
app.include_router(reduce_router)

app.mount(
    "/static", StaticFiles(directory="src/frontend", html=False), name="frontend-static"
)