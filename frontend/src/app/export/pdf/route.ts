import chromium from '@sparticuz/chromium';
import puppeteer, { type Browser } from 'puppeteer-core';
import type { CheckResultReportProps } from '@/features/check/CheckResultReport';
import type { CheckResults, ModuleResult } from '@/features/check/types';

export const runtime = 'nodejs';
export const maxDuration = 60;

const MAX_BYTES = 2 * 1024 * 1024;
let activeRenders = 0;
let executable: Promise<string> | undefined;

class InvalidRequest extends Error {
  constructor(readonly status = 400) { super('Data ekspor PDF tidak valid.'); }
}

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new InvalidRequest();
  return value as Record<string, unknown>;
}

function string(value: unknown, limit: number): string {
  if (typeof value !== 'string' || value.length > limit) throw new InvalidRequest();
  return value;
}

async function readReport(request: Request): Promise<Omit<CheckResultReportProps, 'exportMode'>> {
  if (Number(request.headers.get('content-length')) > MAX_BYTES) throw new InvalidRequest(413);
  const reader = request.body?.getReader();
  if (!reader) throw new InvalidRequest();
  const chunks: Uint8Array[] = [];
  let bytes = 0;
  const deadline = setTimeout(() => { void reader.cancel(); }, 10000);
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > MAX_BYTES) { await reader.cancel(); throw new InvalidRequest(413); }
      chunks.push(value);
    }
  } finally { clearTimeout(deadline); reader.releaseLock(); }
  let parsed: unknown;
  try { parsed = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
  catch { throw new InvalidRequest(); }
  const input = object(parsed);
  const result = object(input.result);
  const modules = Object.entries(object(result.results));
  if (modules.length > 24) throw new InvalidRequest();
  const results: Record<string, ModuleResult> = Object.create(null);
  let messageCount = 0;
  for (const [key, value] of modules) {
    if (!/^[a-z_]+$/.test(key)) throw new InvalidRequest();
    if (value == null) continue;
    const mod = object(value);
    const clean: ModuleResult = {};
    if (mod.status !== undefined) clean.status = string(mod.status, 30);
    if (mod.message !== undefined) clean.message = string(mod.message, 100000);
    if (mod.messages !== undefined) {
      if (!Array.isArray(mod.messages)) throw new InvalidRequest();
      messageCount += mod.messages.length;
      if (messageCount > 4000) throw new InvalidRequest(413);
      clean.messages = mod.messages.map((value) => {
        const msg = object(value);
        return { level: string(msg.level, 30), text: string(msg.text, 100000) };
      });
    }
    if (key === 'structure' && mod.schema != null) {
      const schema = object(mod.schema);
      if (schema.code !== undefined) clean.schema = { code: string(schema.code, 100) };
    }
    results[key] = clean;
  }
  return {
    result: {
      submission_id: string(result.submission_id, 200),
      status: string(result.status, 30),
      overall_status: string(result.overall_status, 30),
      results: results as CheckResults['results'],
    },
    sourceFileName: input.sourceFileName === undefined ? undefined : string(input.sourceFileName, 500),
    schemaLabel: input.schemaLabel === undefined ? undefined : string(input.schemaLabel, 100),
    reportLabel: input.reportLabel === undefined ? undefined : string(input.reportLabel, 100),
  };
}

export async function POST(request: Request) {
  const headers = { 'Cache-Control': 'no-store' };
  const origin = request.headers.get('origin');
  let originMatches = true;
  if (origin) {
    try { originMatches = new URL(origin).host === request.headers.get('host'); }
    catch { originMatches = false; }
  }
  if (request.headers.get('sec-fetch-site') === 'cross-site' ||
      !originMatches) {
    return Response.json({ error: 'Permintaan tidak diizinkan.' }, { status: 403, headers });
  }
  if (!request.headers.get('content-type')?.startsWith('application/json')) {
    return Response.json({ error: 'Gunakan data JSON.' }, { status: 415, headers });
  }
  if (activeRenders >= 2) {
    return Response.json({ error: 'Ekspor sedang sibuk. Coba kembali.' }, { status: 429, headers });
  }
  activeRenders++;
  let browser: Browser | undefined;
  let deadline: ReturnType<typeof setTimeout> | undefined;
  try {
    const report = await readReport(request);
    // Fixed local origin, never a user-supplied URL. Only our report and assets load.
    const renderOrigin = new URL(process.env.PDF_RENDER_ORIGIN ?? 'http://127.0.0.1:3000').origin;
    executable ??= chromium.executablePath().catch((error) => { executable = undefined; throw error; });
    browser = await puppeteer.launch({
      executablePath: await executable,
      args: chromium.args,
      headless: true,
      timeout: 20000,
    });
    deadline = setTimeout(() => { void browser?.close().catch(() => {}); }, 40000);
    const page = await browser.newPage();
    await page.setViewport({ width: 976, height: 900 });
    await page.setRequestInterception(true);
    page.on('request', (resource) => {
      const url = new URL(resource.url());
      const allowed = url.origin === renderOrigin &&
        (url.pathname === '/export/report' || url.pathname.startsWith('/_next/'));
      void (allowed || url.protocol === 'data:' ? resource.continue() : resource.abort()).catch(() => {});
    });
    await page.evaluateOnNewDocument((data) => { window.__CHECK_PDF_REPORT__ = data; }, report);
    await page.goto(`${renderOrigin}/export/report`, { waitUntil: 'networkidle0', timeout: 20000 });
    await page.waitForSelector('html[data-pdf-ready="true"]', { timeout: 15000 });
    const pdf = await page.pdf({
      format: 'A4', preferCSSPageSize: true, printBackground: true,
      displayHeaderFooter: false, timeout: 20000,
    });
    const name = (report.sourceFileName ?? report.result.submission_id).replace(/\.[^.]+$/, '')
      .replace(/[^a-zA-Z0-9-_]+/g, '_').replace(/^_+|_+$/g, '') || 'dokumen';
    return new Response(new Uint8Array(pdf), {
      headers: { ...headers, 'Content-Type': 'application/pdf',
        'Content-Disposition': `attachment; filename="hasil-pengecekan-${name}.pdf"` },
    });
  } catch (error) {
    const status = error instanceof InvalidRequest ? error.status : 500;
    if (status === 500) console.error('[pdf-export] Rendering failed:', error instanceof Error ? error.message : 'Unknown error');
    return Response.json({ error: status === 500 ? 'PDF gagal dibuat. Silakan coba kembali.' : 'Data ekspor PDF tidak valid.' }, { status, headers });
  } finally {
    if (deadline) clearTimeout(deadline);
    await browser?.close().catch(() => {});
    activeRenders--;
  }
}
