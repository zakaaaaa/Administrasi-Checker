"""FastAPI app entrypoint."""
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.auth import verify_password, generate_token
from app.db import get_cursor

app = FastAPI(title="Administrasi Checker API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Static catalog
# ---------------------------------------------------------------------------

COMPETITIONS = [
    {"code": "PKM", "name": "Program Kreativitas Mahasiswa", "active": True},
    {"code": "P2MW", "name": "Program Pembinaan Mahasiswa Wirausaha", "active": False},
    {"code": "PPK_ORMAWA", "name": "Penguatan Kapasitas Ormawa", "active": False},
    {"code": "BIMA", "name": "Sistem Penelitian & Pengabdian Kemdikbud", "active": False},
]
REPORT_TYPES = {
    "PKM": [
        {"code": "PROPOSAL", "name": "Proposal", "active": True},
        {"code": "PROGRESS_REPORT", "name": "Laporan Kemajuan", "active": False},
        {"code": "FINAL_REPORT", "name": "Laporan Akhir", "active": False},
        {"code": "SCIENTIFIC_ARTICLE", "name": "Artikel Ilmiah", "active": True},
    ],
}
SCHEMAS = {
    ("PKM", "PROPOSAL"): [
        {"code": "PKM-KC", "name": "Karsa Cipta", "active": True},
        {"code": "PKM-K", "name": "Kewirausahaan", "active": False},
        {"code": "PKM-RE", "name": "Riset Eksakta", "active": False},
        {"code": "PKM-RSH", "name": "Riset Sosial Humaniora", "active": False},
        {"code": "PKM-PM", "name": "Pengabdian kepada Masyarakat", "active": False},
        {"code": "PKM-PI", "name": "Penerapan Iptek", "active": False},
        {"code": "PKM-KI", "name": "Karya Inovatif", "active": False},
        {"code": "PKM-GFT", "name": "Gagasan Futuristik Tertulis", "active": False},
        {"code": "PKM-VGK", "name": "Video Gagasan Konstruktif", "active": False},
    ],
    ("PKM", "SCIENTIFIC_ARTICLE"): [
        {"code": "PKM-AI", "name": "Artikel Ilmiah", "active": True},
    ],
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    admin_id: str
    username: str


class GenerateTokenRequest(BaseModel):
    admin_id: str


class GenerateTokenResponse(BaseModel):
    token: str


class GenerateBulkTokenRequest(BaseModel):
    admin_id: str
    count: int


class GenerateBulkTokenResponse(BaseModel):
    tokens: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_admin(admin_id: str) -> dict:
    """Pastikan admin_id valid; return row admin."""
    with get_cursor() as cur:
        cur.execute("SELECT id, username FROM admins WHERE id = %s", (admin_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(401, "Admin tidak ditemukan / tidak login")
    return row


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/competitions")
def list_competitions():
    return {"competitions": COMPETITIONS}


@app.get("/api/competitions/{code}/report-types")
def list_report_types(code: str):
    if code not in REPORT_TYPES:
        raise HTTPException(404, f"Competition '{code}' not found")
    return {"report_types": REPORT_TYPES[code]}


@app.get("/api/schemas")
def list_schemas(competition: str, report: str):
    key = (competition, report)
    if key not in SCHEMAS:
        raise HTTPException(404, f"No schemas for {competition}/{report}")
    return {"schemas": SCHEMAS[key]}


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@app.post("/api/admin/login", response_model=AdminLoginResponse)
def admin_login(req: AdminLoginRequest):
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, username, password_hash FROM admins WHERE username = %s",
            (req.username,),
        )
        row = cur.fetchone()
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(401, "Username atau password salah")
    return AdminLoginResponse(admin_id=str(row["id"]), username=row["username"])


@app.post("/api/admin/tokens", response_model=GenerateTokenResponse)
def generate_admin_token(req: GenerateTokenRequest):
    admin = _verify_admin(req.admin_id)
    for _ in range(5):
        token = generate_token()
        try:
            with get_cursor() as cur:
                cur.execute(
                    "INSERT INTO tokens (token, created_by) VALUES (%s, %s) RETURNING id",
                    (token, admin["id"]),
                )
            return GenerateTokenResponse(token=token)
        except Exception:
            continue
    raise HTTPException(500, "Gagal generate token unik")


@app.post("/api/admin/tokens/bulk", response_model=GenerateBulkTokenResponse)
def generate_bulk_tokens(req: GenerateBulkTokenRequest):
    if req.count < 2 or req.count > 500:
        raise HTTPException(400, "Jumlah token harus antara 2–500")
    admin = _verify_admin(req.admin_id)
    tokens: list[str] = []
    for _ in range(req.count):
        generated = False
        for _ in range(5):
            token = generate_token()
            try:
                with get_cursor() as cur:
                    cur.execute(
                        "INSERT INTO tokens (token, created_by) VALUES (%s, %s)",
                        (token, admin["id"]),
                    )
                tokens.append(token)
                generated = True
                break
            except Exception:
                continue
        if not generated:
            raise HTTPException(500, "Gagal generate token unik")
    return GenerateBulkTokenResponse(tokens=tokens)


@app.get("/api/admin/tokens")
def list_tokens(admin_id: str):
    _verify_admin(admin_id)
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT token, created_at, consumed_at
            FROM tokens
            ORDER BY created_at DESC
            LIMIT 500
            """,
        )
        rows = cur.fetchall()
    return {
        "tokens": [
            {
                "token": r["token"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "used": r["consumed_at"] is not None,
                "used_at": r["consumed_at"].isoformat() if r["consumed_at"] else None,
            }
            for r in rows
        ]
    }


# ---------------------------------------------------------------------------
# Submission endpoint
# ---------------------------------------------------------------------------

import json
import uuid
from pathlib import Path
from fastapi import UploadFile, File, Form
from app.services.orchestrator import CheckRequest, run_all_checks, UnsupportedSchemaError

UPLOAD_DIR = Path(__file__).parent.parent / "storage" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


@app.post("/api/check")
def submit_check(
    token: str = Form(...),
    competition: str = Form(...),
    report_type: str = Form(...),
    schema_code: str = Form(...),
    file: UploadFile = File(...),
):
    # 1. Validate file extension
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(400, "File harus berformat .docx")

    # 2. Read file & check size
    content = file.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File terlalu besar (max {MAX_FILE_SIZE // 1024 // 1024} MB)")
    if len(content) == 0:
        raise HTTPException(400, "File kosong")

    # 3. Verify token (atomic: select + mark consumed in one tx)
    submission_id = str(uuid.uuid4())
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, consumed_at FROM tokens WHERE token = %s FOR UPDATE",
            (token,),
        )
        token_row = cur.fetchone()
        if not token_row:
            raise HTTPException(401, "Token tidak valid")
        if token_row["consumed_at"] is not None:
            raise HTTPException(401, "Token sudah pernah digunakan")
        token_id = token_row["id"]

        # 4. Save file
        file_path = UPLOAD_DIR / f"{submission_id}.docx"
        file_path.write_bytes(content)

        # 5. Insert submission
        cur.execute(
            """
            INSERT INTO submissions
                (id, token_id, competition, report_type, schema_code,
                 original_filename, file_path, file_size_bytes, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'processing')
            """,
            (submission_id, token_id, competition, report_type, schema_code,
             file.filename, str(file_path), len(content)),
        )

        # 6. Mark token consumed
        cur.execute(
            "UPDATE tokens SET consumed_at = NOW(), consumed_by_submission_id = %s WHERE id = %s",
            (submission_id, token_id),
        )

    # 7. Run checks (outside DB transaction — bisa lama)
    try:
        req = CheckRequest(
            docx_path=str(file_path),
            competition=competition,
            report_type=report_type,
            schema_code=schema_code,
        )
        results = run_all_checks(req)
    except UnsupportedSchemaError as e:
        with get_cursor() as cur:
            cur.execute(
                "UPDATE submissions SET status='failed', error_message=%s WHERE id=%s",
                (str(e), submission_id),
            )
        raise HTTPException(400, str(e))
    except Exception as e:
        with get_cursor() as cur:
            cur.execute(
                "UPDATE submissions SET status='failed', error_message=%s WHERE id=%s",
                (str(e), submission_id),
            )
        raise HTTPException(500, f"Gagal memproses dokumen: {e}")

    # 8. Save results — modul yang tidak dijalankan disimpan NULL di DB,
    # dan tidak dimasukkan ke payload response.
    module_to_column = {
        "structure": "structure_result",
        "physical_sheet": "physical_sheet_result",
        "format": "format_result",
        "page_numbering": "page_numbering_result",
        "budget": "budget_result",
        "reference": "reference_result",
        "ai_content": "ai_content_result",
        "ai_format": "ai_format_result",
    }

    def _module_payload(key: str):
        payload = results.get(key)
        return json.dumps(payload) if payload is not None else None

    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO results
                (submission_id, structure_result, physical_sheet_result,
                 format_result, page_numbering_result, budget_result,
                 reference_result, ai_content_result, ai_format_result,
                 overall_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (submission_id,
             _module_payload("structure"),
             _module_payload("physical_sheet"),
             _module_payload("format"),
             _module_payload("page_numbering"),
             _module_payload("budget"),
             _module_payload("reference"),
             _module_payload("ai_content"),
             _module_payload("ai_format"),
             results["overall_status"]),
        )
        cur.execute(
            "UPDATE submissions SET status='completed', completed_at=NOW() WHERE id=%s",
            (submission_id,),
        )

    response_results = {
        key: results[key]
        for key in module_to_column
        if key in results
    }

    return {
        "submission_id": submission_id,
        "status": "completed",
        "overall_status": results["overall_status"],
        "results": response_results,
    }
