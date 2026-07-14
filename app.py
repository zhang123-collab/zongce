from zongce.core import *
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError

app = FastAPI(title="综测自动算分系统", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=os.path.join(PROJECT_DIR, "static")), name="static")

cors_origins = [
    item.strip()
    for item in os.environ.get(
        "ZONGCE_CORS_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:5173,http://localhost:5173"
    ).split(",")
    if item.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/docs/oauth2-redirect", include_in_schema=False)
async def swagger_oauth2_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    resp = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title="综测自动算分系统 - Swagger UI",
        oauth2_redirect_url="/docs/oauth2-redirect",
    )
    html = resp.body.decode("utf-8") if isinstance(resp.body, bytes) else resp.body
    custom = """
<style>
.z-hide-example .responses-wrapper .example,
.z-hide-example .responses-wrapper .model-example,
.z-hide-example .responses-wrapper .examples-select,
.z-hide-example .responses-wrapper .responses-examples {
    display: none !important;
}
</style>
<script>
(function() {
  function hasRealResponse(op) {
    var wrap = op.querySelector('.responses-wrapper, .live-responses-wrapper');
    if (!wrap) return false;
    var selectors = [
      'pre code', 'pre.microlight', 'code.language-json',
      '.renderedMarkdown pre', 'table.live-responses-table',
      '.live-responses-table .response-col_body',
      '.swagger-ui .responses-table tbody'
    ];
    for (var i = 0; i < selectors.length; i++) {
      var el = wrap.querySelector(selectors[i]);
      if (el) {
        var t = (el.textContent || '').trim();
        if (t && t.length > 30) return true;
      }
    }
    return false;
  }
  function updateAll() {
    var ops = document.querySelectorAll('.opblock, .operation-tag-content .opblock-summary');
    document.querySelectorAll('.opblock').forEach(function(op) {
      op.classList.toggle('z-hide-example', hasRealResponse(op));
    });
  }
  function start() {
    if (!document.body) return false;
    updateAll();
    setInterval(updateAll, 300);
    var obs = new MutationObserver(updateAll);
    obs.observe(document.body, { childList: true, subtree: true, characterData: true });
    return true;
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
</script>
    """
    html = html.replace("</body>", custom + "\n</body>")
    return HTMLResponse(content=html)


from zongce.routers.members import router as members_router
from zongce.routers.applications import (
    ApplicationCreate,
    ApplicationUpdate,
    create_application,
    router as applications_router,
    submit_application,
    update_application,
    upload_file,
)

from zongce.routers.audits import AuditPassReq, audit_pass, router as audits_router
from zongce.routers.rules import router as rules_router
from zongce.routers.admin import router as admin_router
from zongce.routers.accounting import router as accounting_router
from zongce.routers.batches import router as batches_router
from zongce.routers.ai import router as ai_router
from zongce.routers.publications import router as publications_router
from zongce.routers.reports import router as reports_router

app.include_router(members_router)
app.include_router(applications_router)
app.include_router(audits_router)
app.include_router(rules_router)
app.include_router(admin_router)
app.include_router(accounting_router)
app.include_router(batches_router)
app.include_router(ai_router)
app.include_router(publications_router)
app.include_router(reports_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail, "data": None}
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [
        {
            "field": ".".join(str(part) for part in error.get("loc", [])[1:]),
            "message": error.get("msg", "参数不合法"),
            "type": error.get("type", "validation_error"),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "请求参数校验失败",
            "data": {"errors": errors},
        },
    )


STATIC_INDEX = os.path.join(PROJECT_DIR, "static", "index.html")


@app.get("/", tags=["🔓 0-登录与公共"], summary="前端管理系统首页")
def read_root(request: Request):
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return ApiResponse.success({"message": "后端启动成功"})
    return FileResponse(STATIC_INDEX, media_type="text/html")


from zongce.seed import initialize_demo_data
from zongce.accounting_service import refresh_rank_cache

initialize_demo_data()
with SessionLocal() as startup_db:
    refresh_rank_cache(startup_db)
    startup_db.commit()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
