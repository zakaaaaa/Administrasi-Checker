-- Akun reviewer: login di /reviewer, dikelola admin dari menu "Kelola Reviewer".
-- Idempoten — aman dijalankan ulang.

CREATE TABLE IF NOT EXISTS reviewers (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username      varchar(50)  NOT NULL UNIQUE,
    full_name     varchar(120) NOT NULL,
    password_hash text         NOT NULL,
    is_active     boolean      NOT NULL DEFAULT true,
    created_by    uuid REFERENCES admins(id) ON DELETE SET NULL,
    created_at    timestamptz  NOT NULL DEFAULT now(),
    updated_at    timestamptz  NOT NULL DEFAULT now()
);

-- Tabel ini menyimpan hash password. Database-nya proyek Supabase yang juga
-- melayani REST API publik (anon key), jadi tutup akses anon/authenticated.
-- Backend konek sebagai postgres (BYPASSRLS) sehingga tidak terpengaruh.
ALTER TABLE reviewers ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON reviewers FROM anon, authenticated;

CREATE INDEX IF NOT EXISTS submissions_reviewer_user_id_idx
    ON submissions (reviewer_user_id);
