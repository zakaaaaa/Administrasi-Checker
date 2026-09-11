"""FastAPI app entrypoint."""
# Load .env PALING AWAL — sebelum import apapun yang butuh env var
# (mis. Google Cloud Vision client yang baca GOOGLE_APPLICATION_CREDENTIALS).
from dotenv import load_dotenv
load_dotenv()

import re
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import psycopg2

from app.auth import hash_password, verify_password, generate_token
from app.db import get_cursor
from app.storage import upload_docx_async


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Preload Google Cloud Vision client.
    try:
        import asyncio
        from app.services.biodata_date_checker import preload_ocr_model
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, preload_ocr_model)
        print("[startup] OCR engine ready (Google Vision).")
    except Exception as e:
        print(f"[startup] OCR preload skipped: {e}")
    yield


app = FastAPI(title="Administrasi Checker API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://192.168.1.20:3000"],
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
        {"code": "PROGRESS_REPORT", "name": "Laporan Kemajuan", "active": True},
        {"code": "FINAL_REPORT", "name": "Laporan Akhir", "active": True},
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
        {"code": "PKM-VGK", "name": "Video Gagasan Konstruktif", "active": True},
    ],
    ("PKM", "SCIENTIFIC_ARTICLE"): [
        {"code": "PKM-KC", "name": "Karsa Cipta", "active": True},
        {"code": "PKM-K", "name": "Kewirausahaan", "active": True},
        {"code": "PKM-RE", "name": "Riset Eksakta", "active": True},
        {"code": "PKM-RSH", "name": "Riset Sosial Humaniora", "active": True},
        {"code": "PKM-PM", "name": "Pengabdian kepada Masyarakat", "active": True},
        {"code": "PKM-PI", "name": "Penerapan Iptek", "active": True},
        {"code": "PKM-KI", "name": "Karya Inovatif", "active": True},
        {"code": "PKM-AI", "name": "Artikel Ilmiah", "active": True},
    ],
}

# Laporan Kemajuan & Laporan Akhir: 8 skema pendanaan yang sama.
_LAPORAN_SCHEMAS_CATALOG = [
    {"code": "PKM-KC", "name": "Karsa Cipta", "active": True},
    {"code": "PKM-K", "name": "Kewirausahaan", "active": True},
    {"code": "PKM-RE", "name": "Riset Eksakta", "active": True},
    {"code": "PKM-RSH", "name": "Riset Sosial Humaniora", "active": True},
    {"code": "PKM-PM", "name": "Pengabdian kepada Masyarakat", "active": True},
    {"code": "PKM-PI", "name": "Penerapan Iptek", "active": True},
    {"code": "PKM-KI", "name": "Karya Inovatif", "active": True},
    {"code": "PKM-VGK", "name": "Video Gagasan Konstruktif", "active": True},
]
SCHEMAS[("PKM", "PROGRESS_REPORT")] = _LAPORAN_SCHEMAS_CATALOG
SCHEMAS[("PKM", "FINAL_REPORT")] = _LAPORAN_SCHEMAS_CATALOG


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

def _is_uuid(value: Optional[str]) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def _verify_admin(admin_id: str) -> dict:
    """Pastikan admin_id valid; return row admin."""
    if not _is_uuid(admin_id):
        raise HTTPException(401, "Admin tidak ditemukan / tidak login")
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
        if not row:
            # Akun reviewer tidak punya akses Admin Panel. Beri tahu dengan
            # jelas — tapi hanya kalau password-nya benar.
            cur.execute(
                "SELECT password_hash FROM reviewers WHERE username = %s",
                (req.username.strip().lower(),),
            )
            reviewer = cur.fetchone()
            if reviewer and verify_password(req.password, reviewer["password_hash"]):
                raise HTTPException(
                    403,
                    "Akun reviewer tidak punya akses ke Admin Panel. "
                    "Silakan masuk lewat halaman /reviewer.",
                )
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
def list_tokens(
    admin_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=5, le=50),
    q: str = "",
    status: str = "all",
    date_from: str = "",
    date_to: str = "",
):
    _verify_admin(admin_id)
    if status not in ("all", "used", "unused"):
        raise HTTPException(400, "Status token tidak valid")

    where_parts: list[str] = []
    params: list = []

    query = q.strip()
    if query:
        compact_query = "".join(ch for ch in query if ch.isalnum())
        if compact_query:
            where_parts.append("(token ILIKE %s OR regexp_replace(token, '[^A-Za-z0-9]', '', 'g') ILIKE %s)")
            params.append(f"%{query}%")
            params.append(f"%{compact_query}%")
        else:
            where_parts.append("token ILIKE %s")
            params.append(f"%{query}%")
    if status == "used":
        where_parts.append("consumed_at IS NOT NULL")
    elif status == "unused":
        where_parts.append("consumed_at IS NULL")
    if date_from:
        where_parts.append("created_at >= %s::date")
        params.append(date_from)
    if date_to:
        where_parts.append("created_at < (%s::date + INTERVAL '1 day')")
        params.append(date_to)

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    offset = (page - 1) * page_size

    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE consumed_at IS NOT NULL) AS used_count
            FROM tokens
            {where_sql}
            """,
            tuple(params),
        )
        count_row = cur.fetchone()
        total = count_row["total"]
        used_count = count_row["used_count"]

        cur.execute(
            f"""
            SELECT token, created_at, consumed_at
            FROM tokens
            {where_sql}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (*params, page_size, offset),
        )
        rows = cur.fetchall()
    total_pages = (total + page_size - 1) // page_size if total else 1
    return {
        "tokens": [
            {
                "token": r["token"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "used": r["consumed_at"] is not None,
                "used_at": r["consumed_at"].isoformat() if r["consumed_at"] else None,
            }
            for r in rows
        ],
        "total": total,
        "used_count": used_count,
        "unused_count": total - used_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# ---------------------------------------------------------------------------
# Submission endpoint
# ---------------------------------------------------------------------------

import json
import uuid
from pathlib import Path
from fastapi import UploadFile, File, Form
from app.services.orchestrator import CheckRequest, run_all_checks, UnsupportedSchemaError


# ---------------------------------------------------------------------------
# Upload history endpoint
# ---------------------------------------------------------------------------

def _parse_col(val) -> dict:
    if val is None:
        return {}
    if isinstance(val, dict):
        return val
    try:
        return json.loads(val)
    except Exception:
        return {}


def _count_messages(mod: dict) -> tuple[int, int]:
    fail, warn = 0, 0
    msgs = mod.get("messages", [])
    if isinstance(msgs, list):
        for m in msgs:
            lvl = m.get("level", "") if isinstance(m, dict) else ""
            if lvl in ("fail", "error"):
                fail += 1
            elif lvl == "warning":
                warn += 1
    elif isinstance(mod.get("message"), str) and mod.get("status") in ("fail", "error"):
        fail += 1
    return fail, warn


@app.get("/api/admin/uploads")
def list_uploads(
    admin_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=5, le=50),
    q: str = "",
):
    _verify_admin(admin_id)
    query = q.strip()
    where_sql = ""
    params: list = []
    if query:
        where_sql = """
            WHERE (
                s.original_filename ILIKE %s
                OR s.schema_code ILIKE %s
                OR s.report_type ILIKE %s
                OR COALESCE(r.overall_status, '') ILIKE %s
                OR CAST(s.id AS TEXT) ILIKE %s
            )
        """
        like = f"%{query}%"
        params.extend([like, like, like, like, like])

    offset = (page - 1) * page_size
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM submissions s
            LEFT JOIN results r ON s.id = r.submission_id
            {where_sql}
            """,
            tuple(params),
        )
        total = cur.fetchone()["total"]

        cur.execute(
            f"""
            SELECT
                s.id            AS submission_id,
                s.original_filename,
                s.schema_code,
                s.report_type,
                s.status,
                s.completed_at,
                r.overall_status,
                r.structure_result,
                r.physical_sheet_result,
                r.format_result,
                r.page_numbering_result,
                r.budget_result,
                r.reference_result
            FROM submissions s
            LEFT JOIN results r ON s.id = r.submission_id
            {where_sql}
            ORDER BY s.completed_at DESC NULLS LAST
            LIMIT %s OFFSET %s
            """,
            (*params, page_size, offset),
        )
        rows = cur.fetchall()

    RESULT_KEYS = [
        ("structure",       "structure_result"),
        ("physical_sheet",  "physical_sheet_result"),
        ("format",          "format_result"),
        ("page_numbering",  "page_numbering_result"),
        ("budget",          "budget_result"),
        ("reference",       "reference_result"),
    ]

    uploads = []
    for row in rows:
        fail_total, warn_total = 0, 0
        results: dict = {}
        for mod_key, col_key in RESULT_KEYS:
            mod = _parse_col(row.get(col_key))
            results[mod_key] = mod
            f, w = _count_messages(mod)
            fail_total += f
            warn_total += w

        uploads.append({
            "submission_id":    str(row["submission_id"]),
            "original_filename": row["original_filename"],
            "schema_code":      row["schema_code"],
            "report_type":      row["report_type"],
            "status":           row["status"],
            "completed_at":     row["completed_at"].isoformat() if row["completed_at"] else None,
            "overall_status":   row["overall_status"],
            "fail_count":       fail_total,
            "warn_count":       warn_total,
            "results":          results,
        })

    total_pages = (total + page_size - 1) // page_size if total else 1
    return {
        "uploads": uploads,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# ---------------------------------------------------------------------------
# Overview / stats endpoint
# ---------------------------------------------------------------------------

@app.get("/api/admin/overview")
def get_overview(admin_id: str):
    _verify_admin(admin_id)
    with get_cursor() as cur:
        # Tokens
        cur.execute("SELECT COUNT(*) AS total FROM tokens")
        total_tokens = cur.fetchone()["total"]

        cur.execute("SELECT COUNT(*) AS used FROM tokens WHERE consumed_at IS NOT NULL")
        tokens_used = cur.fetchone()["used"]

        # Submissions
        cur.execute("SELECT COUNT(*) AS total FROM submissions WHERE status = 'completed'")
        total_submissions = cur.fetchone()["total"]

        cur.execute(
            "SELECT COUNT(*) AS today FROM submissions WHERE status = 'completed' AND completed_at::date = CURRENT_DATE"
        )
        submissions_today = cur.fetchone()["today"]

        # Status breakdown
        cur.execute(
            "SELECT overall_status, COUNT(*) AS cnt FROM results GROUP BY overall_status"
        )
        status_rows = cur.fetchall()
        status_map = {r["overall_status"]: r["cnt"] for r in status_rows if r["overall_status"]}

        # By schema
        cur.execute(
            """
            SELECT schema_code, COUNT(*) AS cnt
            FROM submissions
            WHERE status = 'completed'
            GROUP BY schema_code
            ORDER BY cnt DESC
            """
        )
        by_schema = [{"schema_code": r["schema_code"], "count": r["cnt"]} for r in cur.fetchall()]

        # Avg processing time (seconds)
        cur.execute(
            """
            SELECT AVG(EXTRACT(EPOCH FROM (completed_at - created_at))) AS avg_sec
            FROM submissions
            WHERE status = 'completed'
              AND completed_at IS NOT NULL
              AND created_at IS NOT NULL
            """
        )
        avg_row = cur.fetchone()
        avg_processing_seconds = (
            round(avg_row["avg_sec"]) if avg_row and avg_row["avg_sec"] else None
        )

        # Recent 5 submissions
        cur.execute(
            """
            SELECT s.original_filename, s.schema_code, s.report_type, s.completed_at,
                   r.overall_status
            FROM submissions s
            LEFT JOIN results r ON s.id = r.submission_id
            WHERE s.status = 'completed'
            ORDER BY s.completed_at DESC NULLS LAST
            LIMIT 5
            """
        )
        recent_rows = cur.fetchall()
        recent = [
            {
                "original_filename": r["original_filename"],
                "schema_code":       r["schema_code"],
                "report_type":       r["report_type"],
                "completed_at":      r["completed_at"].isoformat() if r["completed_at"] else None,
                "overall_status":    r["overall_status"],
            }
            for r in recent_rows
        ]

    return {
        "total_tokens":           total_tokens,
        "tokens_used":            tokens_used,
        "tokens_unused":          total_tokens - tokens_used,
        "total_submissions":      total_submissions,
        "submissions_today":      submissions_today,
        "pass_count":             status_map.get("pass", 0),
        "fail_count":             status_map.get("fail", 0),
        "warning_count":          status_map.get("warning", 0),
        "avg_processing_seconds": avg_processing_seconds,
        "by_schema":              by_schema,
        "recent":                 recent,
    }


@app.get("/api/admin/server-stats")
def get_server_stats(admin_id: str):
    """Metrik real-time VPS (CPU, RAM, disk, jaringan, service, proses)."""
    _verify_admin(admin_id)
    from app.services.server_monitor import collect_server_stats
    return collect_server_stats()


UPLOAD_DIR = Path(__file__).parent.parent / "storage" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 35 * 1024 * 1024  # 35 MB — samakan dengan MAX_FILE_MB frontend & nginx


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

    # 6b. Salin ke R2 di background (file lokal tetap dipakai checker)
    upload_docx_async(
        file_path, submission_id,
        original_filename=file.filename, competition=competition,
        report_type=report_type, schema_code=schema_code, source="token",
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

    # 8. Save results
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO results
                (submission_id, structure_result, physical_sheet_result,
                 format_result, page_numbering_result, budget_result,
                 reference_result, overall_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (submission_id,
             json.dumps(results.get("structure") or {}),
             json.dumps(results.get("physical_sheet") or {}),
             json.dumps(results.get("format") or {}),
             json.dumps(results.get("page_numbering") or {}),
             json.dumps(results.get("budget") or {}),
             json.dumps(results.get("reference") or {}),
             results["overall_status"]),
        )
        cur.execute(
            "UPDATE submissions SET status='completed', completed_at=NOW() WHERE id=%s",
            (submission_id,),
        )

    return {
        "submission_id": submission_id,
        "status": "completed",
        "overall_status": results["overall_status"],
        "results": {
            "structure": results.get("structure"),
            "ai_front_matter": results.get("ai_front_matter"),
            "physical_sheet": results.get("physical_sheet"),
            "format": results.get("format"),
            "page_numbering": results.get("page_numbering"),
            "budget": results.get("budget"),
            "reference": results.get("reference"),
            "luaran": results.get("luaran"),
            "lampiran": results.get("lampiran"),
            "surat_pernyataan": results.get("surat_pernyataan"),
            "biodata_date": results.get("biodata_date"),
            "signature_crop": results.get("signature_crop"),
            "schedule": results.get("schedule"),
            "similarity": results.get("similarity"),
        },
    }


# ---------------------------------------------------------------------------
# Akun reviewer: CRUD oleh admin + login di halaman /reviewer
# ---------------------------------------------------------------------------
# Admin tetap boleh login di /reviewer dengan akun admin-nya (perilaku lama),
# jadi username reviewer tidak boleh bentrok dengan username admin.

_REVIEWER_USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,50}$")
_REVIEWER_PASSWORD_MIN = 8
_REVIEWER_PASSWORD_MAX = 72  # batas bcrypt (byte)
_REVIEWER_NAME_MAX = 120


class ReviewerCreateRequest(BaseModel):
    admin_id: str
    username: str
    full_name: str
    password: str


class ReviewerUpdateRequest(BaseModel):
    admin_id: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None  # None / "" = password tidak diganti
    is_active: Optional[bool] = None


class ReviewerLoginRequest(BaseModel):
    username: str
    password: str


def _clean_reviewer_username(raw: str) -> str:
    username = raw.strip().lower()
    if not _REVIEWER_USERNAME_RE.match(username):
        raise HTTPException(
            400,
            "Username 3–50 karakter, hanya huruf kecil, angka, titik (.), "
            "garis bawah (_), atau tanda hubung (-).",
        )
    return username


def _clean_reviewer_name(raw: str) -> str:
    name = " ".join(raw.split())
    if not name:
        raise HTTPException(400, "Nama lengkap wajib diisi.")
    if len(name) > _REVIEWER_NAME_MAX:
        raise HTTPException(400, f"Nama lengkap maksimal {_REVIEWER_NAME_MAX} karakter.")
    return name


def _check_reviewer_password(password: str) -> str:
    if len(password) < _REVIEWER_PASSWORD_MIN:
        raise HTTPException(400, f"Password minimal {_REVIEWER_PASSWORD_MIN} karakter.")
    if len(password.encode("utf-8")) > _REVIEWER_PASSWORD_MAX:
        raise HTTPException(400, f"Password maksimal {_REVIEWER_PASSWORD_MAX} karakter.")
    return password


def _ensure_reviewer_username_free(cur, username: str, exclude_id: Optional[str] = None) -> None:
    cur.execute("SELECT 1 FROM admins WHERE lower(username) = %s", (username,))
    if cur.fetchone():
        raise HTTPException(409, "Username sudah dipakai akun admin.")
    cur.execute(
        "SELECT 1 FROM reviewers WHERE username = %s AND id IS DISTINCT FROM %s",
        (username, exclude_id),
    )
    if cur.fetchone():
        raise HTTPException(409, "Username sudah dipakai reviewer lain.")


def _reviewer_to_dict(row: dict) -> dict:
    return {
        "id":            str(row["id"]),
        "username":      row["username"],
        "full_name":     row["full_name"],
        "is_active":     row["is_active"],
        "created_at":    row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at":    row["updated_at"].isoformat() if row["updated_at"] else None,
        "check_count":   row.get("check_count") or 0,
        "last_check_at": row["last_check_at"].isoformat() if row.get("last_check_at") else None,
    }


def _verify_reviewer(reviewer_id: Optional[str]) -> dict:
    """Akun yang boleh memakai /api/reviewer/check: reviewer aktif, atau admin."""
    if not _is_uuid(reviewer_id):
        raise HTTPException(401, "Reviewer tidak ditemukan / tidak login")
    with get_cursor() as cur:
        cur.execute("SELECT id, is_active FROM reviewers WHERE id = %s", (reviewer_id,))
        row = cur.fetchone()
        if row:
            if not row["is_active"]:
                raise HTTPException(401, "Akun reviewer dinonaktifkan. Hubungi admin.")
            return {"id": row["id"]}
        cur.execute("SELECT id FROM admins WHERE id = %s", (reviewer_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(401, "Reviewer tidak ditemukan / tidak login")
    return {"id": row["id"]}


@app.get("/api/admin/reviewers")
def list_reviewers(admin_id: str, q: str = ""):
    _verify_admin(admin_id)
    query = q.strip()
    like = f"%{query}%"
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT r.id, r.username, r.full_name, r.is_active, r.created_at, r.updated_at,
                   COUNT(s.id)       AS check_count,
                   MAX(s.created_at) AS last_check_at
            FROM reviewers r
            LEFT JOIN submissions s ON s.reviewer_user_id = r.id
            WHERE (%s = '' OR r.username ILIKE %s OR r.full_name ILIKE %s)
            GROUP BY r.id
            ORDER BY r.created_at DESC
            """,
            (query, like, like),
        )
        rows = cur.fetchall()
    reviewers = [_reviewer_to_dict(r) for r in rows]
    return {
        "reviewers": reviewers,
        "total": len(reviewers),
        "active_count": sum(1 for r in reviewers if r["is_active"]),
    }


@app.post("/api/admin/reviewers", status_code=201)
def create_reviewer(req: ReviewerCreateRequest):
    admin = _verify_admin(req.admin_id)
    username = _clean_reviewer_username(req.username)
    full_name = _clean_reviewer_name(req.full_name)
    password_hash = hash_password(_check_reviewer_password(req.password))
    try:
        with get_cursor() as cur:
            _ensure_reviewer_username_free(cur, username)
            cur.execute(
                """
                INSERT INTO reviewers (username, full_name, password_hash, created_by)
                VALUES (%s, %s, %s, %s)
                RETURNING id, username, full_name, is_active, created_at, updated_at
                """,
                (username, full_name, password_hash, admin["id"]),
            )
            row = cur.fetchone()
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(409, "Username sudah dipakai reviewer lain.")
    return {"reviewer": _reviewer_to_dict(row)}


@app.patch("/api/admin/reviewers/{reviewer_id}")
def update_reviewer(reviewer_id: str, req: ReviewerUpdateRequest):
    _verify_admin(req.admin_id)
    if not _is_uuid(reviewer_id):
        raise HTTPException(404, "Reviewer tidak ditemukan")

    sets: list[str] = []
    params: list = []
    username = None
    if req.username is not None:
        username = _clean_reviewer_username(req.username)
        sets.append("username = %s")
        params.append(username)
    if req.full_name is not None:
        sets.append("full_name = %s")
        params.append(_clean_reviewer_name(req.full_name))
    if req.password:
        sets.append("password_hash = %s")
        params.append(hash_password(_check_reviewer_password(req.password)))
    if req.is_active is not None:
        sets.append("is_active = %s")
        params.append(req.is_active)
    if not sets:
        raise HTTPException(400, "Tidak ada perubahan yang dikirim.")

    try:
        with get_cursor() as cur:
            if username is not None:
                _ensure_reviewer_username_free(cur, username, exclude_id=reviewer_id)
            cur.execute(
                f"""
                UPDATE reviewers SET {", ".join(sets)}, updated_at = NOW()
                WHERE id = %s
                RETURNING id, username, full_name, is_active, created_at, updated_at
                """,
                (*params, reviewer_id),
            )
            row = cur.fetchone()
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(409, "Username sudah dipakai reviewer lain.")
    if not row:
        raise HTTPException(404, "Reviewer tidak ditemukan")
    return {"reviewer": _reviewer_to_dict(row)}


@app.delete("/api/admin/reviewers/{reviewer_id}")
def delete_reviewer(reviewer_id: str, admin_id: str):
    _verify_admin(admin_id)
    if not _is_uuid(reviewer_id):
        raise HTTPException(404, "Reviewer tidak ditemukan")
    # Riwayat upload reviewer tetap disimpan (submissions.reviewer_user_id
    # tidak ber-FK); hanya akunnya yang dihapus sehingga tidak bisa login lagi.
    with get_cursor() as cur:
        cur.execute("DELETE FROM reviewers WHERE id = %s RETURNING id", (reviewer_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Reviewer tidak ditemukan")
    return {"deleted": True, "id": str(row["id"])}


@app.post("/api/reviewer/login")
def reviewer_login(req: ReviewerLoginRequest):
    username = req.username.strip()
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, username, full_name, password_hash, is_active FROM reviewers WHERE username = %s",
            (username.lower(),),
        )
        row = cur.fetchone()
        if row:
            if not verify_password(req.password, row["password_hash"]):
                raise HTTPException(401, "Username atau password salah")
            if not row["is_active"]:
                raise HTTPException(403, "Akun reviewer dinonaktifkan. Hubungi admin.")
            return {
                "reviewer_id": str(row["id"]),
                "username": row["username"],
                "full_name": row["full_name"],
                "role": "reviewer",
            }
        cur.execute(
            "SELECT id, username, password_hash FROM admins WHERE username = %s",
            (username,),
        )
        row = cur.fetchone()
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(401, "Username atau password salah")
    return {
        "reviewer_id": str(row["id"]),
        "username": row["username"],
        "full_name": row["username"],
        "role": "admin",
    }


# ---------------------------------------------------------------------------
# Reviewer endpoint (no token required, authenticated via reviewer_id)
# ---------------------------------------------------------------------------

@app.post("/api/reviewer/check")
def reviewer_check(
    competition: str = Form(...),
    report_type: str = Form(...),
    schema_code: str = Form(...),
    file: UploadFile = File(...),
    reviewer_id: Optional[str] = Form(None),
    admin_id: Optional[str] = Form(None),  # nama field lama — frontend versi sebelumnya
):
    reviewer = _verify_reviewer(reviewer_id or admin_id)

    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(400, "File harus berformat .docx")

    content = file.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File terlalu besar (max {MAX_FILE_SIZE // 1024 // 1024} MB)")
    if len(content) == 0:
        raise HTTPException(400, "File kosong")

    submission_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{submission_id}.docx"
    file_path.write_bytes(content)

    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO submissions
                (id, token_id, competition, report_type, schema_code,
                 original_filename, file_path, file_size_bytes, status, reviewer_user_id)
            VALUES (%s, NULL, %s, %s, %s, %s, %s, %s, 'processing', %s)
            """,
            (submission_id, competition, report_type, schema_code,
             file.filename, str(file_path), len(content), reviewer["id"]),
        )

    upload_docx_async(
        file_path, submission_id,
        original_filename=file.filename, competition=competition,
        report_type=report_type, schema_code=schema_code, source="reviewer",
    )

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

    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO results
                (submission_id, structure_result, physical_sheet_result,
                 format_result, page_numbering_result, budget_result,
                 reference_result, overall_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (submission_id,
             json.dumps(results.get("structure") or {}),
             json.dumps(results.get("physical_sheet") or {}),
             json.dumps(results.get("format") or {}),
             json.dumps(results.get("page_numbering") or {}),
             json.dumps(results.get("budget") or {}),
             json.dumps(results.get("reference") or {}),
             results["overall_status"]),
        )
        cur.execute(
            "UPDATE submissions SET status='completed', completed_at=NOW() WHERE id=%s",
            (submission_id,),
        )

    return {
        "submission_id": submission_id,
        "status": "completed",
        "overall_status": results["overall_status"],
        "results": {
            "structure": results.get("structure"),
            "ai_front_matter": results.get("ai_front_matter"),
            "physical_sheet": results.get("physical_sheet"),
            "format": results.get("format"),
            "page_numbering": results.get("page_numbering"),
            "budget": results.get("budget"),
            "reference": results.get("reference"),
            "luaran": results.get("luaran"),
            "lampiran": results.get("lampiran"),
            "surat_pernyataan": results.get("surat_pernyataan"),
            "biodata_date": results.get("biodata_date"),
            "signature_crop": results.get("signature_crop"),
            "schedule": results.get("schedule"),
            "similarity": results.get("similarity"),
        },
    }
