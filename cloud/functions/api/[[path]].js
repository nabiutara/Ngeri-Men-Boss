import { AbortMultipartUploadCommand, CompleteMultipartUploadCommand, CreateMultipartUploadCommand,
         DeleteObjectCommand, GetObjectCommand, HeadObjectCommand, S3Client, UploadPartCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

const MAX_UPLOAD = 2 * 1024 ** 3;
const PART_SIZE = 64 * 1024 ** 2;
const VIDEO_EXTENSIONS = new Set([".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"]);
let cachedKeys;

function response(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), { status, headers: {
    "Content-Type": "application/json", "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff", ...headers,
  }});
}

function decodeBase64Url(value) {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - value.length % 4) % 4);
  return Uint8Array.from(atob(padded), char => char.charCodeAt(0));
}

async function accessKeys(team) {
  const now = Date.now();
  if (cachedKeys && cachedKeys.team === team && cachedKeys.expires > now) return cachedKeys.keys;
  const issuer = `https://${team}.cloudflareaccess.com`;
  const result = await fetch(`${issuer}/cdn-cgi/access/certs`, { cf: { cacheTtl: 300 } });
  if (!result.ok) throw new Error("Could not load Cloudflare Access signing keys");
  const document = await result.json();
  cachedKeys = { team, expires: now + 300_000, keys: document.keys || [] };
  return cachedKeys.keys;
}

async function requireAccess(request, env) {
  const token = request.headers.get("CF-Access-Jwt-Assertion");
  if (!token || !env.CF_ACCESS_TEAM_DOMAIN || !env.CF_ACCESS_AUD) return false;
  const parts = token.split(".");
  if (parts.length !== 3) return false;
  try {
    const header = JSON.parse(new TextDecoder().decode(decodeBase64Url(parts[0])));
    const claims = JSON.parse(new TextDecoder().decode(decodeBase64Url(parts[1])));
    const issuer = `https://${env.CF_ACCESS_TEAM_DOMAIN}.cloudflareaccess.com`;
    if (header.alg !== "RS256" || claims.iss !== issuer || !Array.isArray(claims.aud) ||
        !claims.aud.includes(env.CF_ACCESS_AUD) || claims.exp <= Date.now() / 1000 ||
        (claims.nbf && claims.nbf > Date.now() / 1000)) return false;
    const jwk = (await accessKeys(env.CF_ACCESS_TEAM_DOMAIN)).find(key => key.kid === header.kid);
    if (!jwk) return false;
    const key = await crypto.subtle.importKey("jwk", jwk,
      { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
    return crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, decodeBase64Url(parts[2]),
      new TextEncoder().encode(`${parts[0]}.${parts[1]}`));
  } catch {
    return false;
  }
}

function equalSecret(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function storage(env) {
  return new S3Client({ region: "auto", endpoint: `https://${env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
    credentials: { accessKeyId: env.R2_ACCESS_KEY_ID, secretAccessKey: env.R2_SECRET_ACCESS_KEY } });
}

function jobResponse(row) {
  return { id: row.id, status: row.status, progress: row.progress, message: row.message,
    error: row.error || undefined, training: row.training_json ? JSON.parse(row.training_json) : undefined };
}

async function proxyModal(env, path, payload, method = "POST") {
  const base = env.MODAL_API_URL?.replace(/\/$/, "");
  if (!base || !env.MODAL_KEY || !env.MODAL_SECRET) throw new Error("Cloud GPU service is not configured");
  return fetch(`${base}${path}`, { method, headers: {
    "Content-Type": "application/json", "Modal-Key": env.MODAL_KEY, "Modal-Secret": env.MODAL_SECRET,
  }, ...(method === "GET" ? {} : { body: JSON.stringify(payload || {}) }) });
}

export async function onRequest({ request, env }) {
  const url = new URL(request.url);
  const path = url.pathname;
  const method = request.method.toUpperCase();

  // Private worker-to-worker callback. User routes always require a valid Access JWT.
  const internal = path.match(/^\/api\/internal\/jobs\/([a-f0-9]{32})$/);
  if (internal && method === "POST") {
    const supplied = (request.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
    if (!equalSecret(supplied, env.CALLBACK_SECRET)) return response({ error: "Unauthorized" }, 401);
    let body;
    try { body = await request.json(); } catch { return response({ error: "Invalid JSON" }, 400); }
    const allowed = new Set(["queued", "running", "training", "completed", "failed", "cancelled"]);
    if (!allowed.has(body.status) || !Number.isInteger(body.progress) || body.progress < 0 || body.progress > 100)
      return response({ error: "Invalid job update" }, 400);
    await env.DB.prepare(`UPDATE jobs SET status=?, progress=?, message=?, error=?, result_key=COALESCE(?,result_key), candidate_key=COALESCE(?,candidate_key), source_sha256=COALESCE(?,source_sha256), training_json=COALESCE(?,training_json), updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND status!='cancelled'`)
      .bind(body.status, body.progress, String(body.message || "").slice(0, 200),
        body.error ? String(body.error).slice(0, 1000) : null, body.result_key || null,
        body.candidate_key || null, body.source_sha256 || null,
        body.training ? JSON.stringify(body.training) : null, internal[1]).run();
    return response({ ok: true });
  }

  if (!path.startsWith("/api/")) return response({ error: "Not found" }, 404);
  if (!await requireAccess(request, env)) return response({ error: "Authentication required" }, 401);

  if (path === "/api/health" && method === "GET") {
    const configured = !!(env.DB && env.R2_ACCOUNT_ID && env.R2_BUCKET && env.R2_ACCESS_KEY_ID &&
      env.R2_SECRET_ACCESS_KEY && env.MODAL_API_URL && env.MODAL_KEY && env.MODAL_SECRET &&
      env.CF_ACCESS_TEAM_DOMAIN && env.CF_ACCESS_AUD && env.CALLBACK_SECRET);
    return response({ app: "touchline-studio", mode: "cloud", ready: configured, training: "candidate-only" });
  }

  if (path === "/api/jobs" && method === "POST") {
    let body;
    try { body = await request.json(); } catch { return response({ error: "Invalid JSON" }, 400); }
    const filename = String(body.filename || "").split(/[\\/]/).pop();
    const dot = filename.lastIndexOf(".");
    const extension = dot >= 0 ? filename.slice(dot).toLowerCase() : "";
    const settings = body.settings || {};
    if (!filename || filename.length > 180 || !VIDEO_EXTENSIONS.has(extension))
      return response({ error: "Choose a supported video file" }, 400);
    if (settings.model_name && settings.model_name !== "football-best.pt")
      return response({ error: "Cloud pseudo-training currently requires football-best.pt" }, 400);
    const confidence = Number(settings.confidence ?? .1), stride = Number(settings.stride ?? 1);
    const imgsz = Number(settings.imgsz ?? 960), tracker = settings.tracker_name ?? "botsort";
    if (!(confidence >= .05 && confidence <= .9) || ![1, 2, 3].includes(stride) ||
        ![640, 960, 1280].includes(imgsz) || !["botsort", "bytetrack"].includes(tracker))
      return response({ error: "Invalid tracking settings" }, 400);
    const id = crypto.randomUUID().replaceAll("-", "");
    const sourceKey = `uploads/${id}/source${extension}`;
    const s3 = storage(env);
    const upload = await s3.send(new CreateMultipartUploadCommand({ Bucket: env.R2_BUCKET,
      Key: sourceKey, ContentType: "application/octet-stream" }));
    if (!upload.UploadId) return response({ error: "Could not initialize secure upload" }, 503);
    const parts = [];
    for (let part = 1; part <= Math.ceil(MAX_UPLOAD / PART_SIZE); part++) {
      parts.push({ part_number: part, upload_url: await getSignedUrl(s3,
        new UploadPartCommand({ Bucket: env.R2_BUCKET, Key: sourceKey,
          UploadId: upload.UploadId, PartNumber: part }), { expiresIn: 86_400 }) });
    }
    const normalized = { confidence, stride, imgsz, tracker_name: tracker, model_name: "football-best.pt" };
    try {
      await env.DB.prepare("INSERT INTO jobs (id,status,progress,message,source_name,source_key,upload_id,settings_json) VALUES (?, 'uploading', 0, 'Waiting for video upload', ?, ?, ?, ?)")
        .bind(id, filename, sourceKey, upload.UploadId, JSON.stringify(normalized)).run();
    } catch (error) {
      await s3.send(new AbortMultipartUploadCommand({ Bucket: env.R2_BUCKET, Key: sourceKey, UploadId: upload.UploadId }));
      throw error;
    }
    return response({ id, part_size: PART_SIZE, parts,
      max_upload_bytes: MAX_UPLOAD, upload_headers: { "Content-Type": "application/octet-stream" } }, 201);
  }

  const jobRoute = path.match(/^\/api\/jobs\/([a-f0-9]{32})(?:\/(complete|start|result|candidate|candidate-manifest))?$/);
  if (jobRoute) {
    const [, id, action] = jobRoute;
    const row = await env.DB.prepare("SELECT * FROM jobs WHERE id=?").bind(id).first();
    if (!row) return response({ error: "Job not found" }, 404);
    if (!action && method === "GET") return response(jobResponse(row));
    if (action === "complete" && method === "POST") {
      if (row.status !== "uploading") return response({ error: "Upload is not awaiting completion" }, 409);
      let body;
      try { body = await request.json(); } catch { return response({ error: "Invalid multipart upload data" }, 400); }
      const parts = body.parts;
      if (!Array.isArray(parts) || parts.length < 1 || parts.length > Math.ceil(MAX_UPLOAD / PART_SIZE))
        return response({ error: "Invalid upload part list" }, 400);
      const valid = parts.every((part, index) => part && part.PartNumber === index + 1 &&
        typeof part.ETag === "string" && /^\"?[A-Fa-f0-9-]{16,80}\"?$/.test(part.ETag));
      if (!valid) return response({ error: "Upload parts are incomplete or invalid" }, 400);
      try {
        await storage(env).send(new CompleteMultipartUploadCommand({ Bucket: env.R2_BUCKET,
          Key: row.source_key, UploadId: row.upload_id,
          MultipartUpload: { Parts: parts.map(part => ({ PartNumber: part.PartNumber, ETag: part.ETag })) } }));
      } catch { return response({ error: "Cloud storage could not finalize the upload" }, 409); }
      await env.DB.prepare("UPDATE jobs SET status='ready',progress=8,message='Video uploaded securely',updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND status='uploading'").bind(id).run();
      return response({ id });
    }
    if (action === "start" && method === "POST") {
      if (row.status !== "ready") return response({ error: "Complete the video upload first" }, 409);
      const s3 = storage(env);
      let object;
      try { object = await s3.send(new HeadObjectCommand({ Bucket: env.R2_BUCKET, Key: row.source_key })); }
      catch { return response({ error: "Video upload is incomplete" }, 409); }
      if (!object.ContentLength || object.ContentLength > MAX_UPLOAD)
        return response({ error: "Video must be smaller than 2 GB" }, 413);
      const reserved = await env.DB.prepare("UPDATE jobs SET status='queued',progress=8,message='Preparing cloud GPU job',updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND status='ready' RETURNING id")
        .bind(id).first();
      if (!reserved) return response({ error: "Job upload was already submitted or cancelled" }, 409);
      const settings = JSON.parse(row.settings_json);
      const modal = await proxyModal(env, "/submit", { job_id: id, source_key: row.source_key,
        source_name: row.source_name, settings: { ...settings, model_name: "football-best.pt" } });
      if (!modal.ok) {
        const detail = (await modal.text()).slice(0, 500);
        await env.DB.prepare("UPDATE jobs SET status='failed', message='Could not queue GPU job', error=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?")
          .bind(detail, id).run();
        try { await s3.send(new DeleteObjectCommand({ Bucket: env.R2_BUCKET, Key: row.source_key })); } catch {}
        return response({ error: "Could not queue the cloud GPU job" }, 503);
      }
      await env.DB.prepare("UPDATE jobs SET message='Queued for cloud GPU',updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?").bind(id).run();
      return response({ id });
    }
    if (action === "result" && method === "GET") {
      if (row.status !== "completed" || !row.result_key) return response({ error: "Results are not ready" }, 409);
      const object = await storage(env).send(new GetObjectCommand({ Bucket: env.R2_BUCKET, Key: row.result_key }));
      return new Response(object.Body.transformToWebStream(), { headers: {
        "Content-Type": "application/json", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
      }});
    }
    if (action === "candidate" && method === "GET") {
      if (row.status !== "completed" || !row.candidate_key)
        return response({ error: "This job has no candidate checkpoint" }, 404);
      const object = await storage(env).send(new GetObjectCommand({ Bucket: env.R2_BUCKET, Key: row.candidate_key }));
      return new Response(object.Body.transformToWebStream(), { headers: {
        "Content-Type": "application/octet-stream",
        "Content-Disposition": `attachment; filename="touchline-candidate-${id}.pt"`,
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
      }});
    }
    if (action === "candidate-manifest" && method === "GET") {
      const manifestKey = row.training_json ? JSON.parse(row.training_json).manifest_key : null;
      if (row.status !== "completed" || !manifestKey)
        return response({ error: "This job has no candidate provenance manifest" }, 404);
      const object = await storage(env).send(new GetObjectCommand({ Bucket: env.R2_BUCKET, Key: manifestKey }));
      return new Response(object.Body.transformToWebStream(), { headers: {
        "Content-Type": "application/json",
        "Content-Disposition": `attachment; filename="touchline-candidate-${id}-provenance.json"`,
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
      }});
    }
    if (!action && method === "DELETE") {
      if (["completed", "cancelled"].includes(row.status)) return response({ message: "Job already finished" });
      if (row.status === "failed") {
        try { await storage(env).send(new DeleteObjectCommand({ Bucket: env.R2_BUCKET, Key: row.source_key })); }
        catch { return response({ error: "Job failed; source cleanup is pending storage lifecycle" }, 202); }
        return response({ message: "Failed job source deleted" });
      }
      if (row.status !== "uploading" && row.status !== "ready") {
        try {
          const cancelled = await proxyModal(env, `/jobs/${id}/cancel`, {});
          if (!cancelled.ok || !(await cancelled.json()).cancelled)
            return response({ error: "The GPU job could not be cancelled; it may already be finishing" }, 409);
        } catch { return response({ error: "The GPU service could not confirm cancellation" }, 503); }
      }
      await env.DB.prepare("UPDATE jobs SET status='cancelled',message='Cancellation requested',updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?").bind(id).run();
      try {
        const s3 = storage(env);
        if (row.status === "uploading")
          await s3.send(new AbortMultipartUploadCommand({ Bucket: env.R2_BUCKET, Key: row.source_key, UploadId: row.upload_id }));
        await s3.send(new DeleteObjectCommand({ Bucket: env.R2_BUCKET, Key: row.source_key }));
      } catch {
        return response({ message: "Cancellation requested", cleanup: "pending-storage-lifecycle" }, 202);
      }
      return response({ message: "Cancellation requested" });
    }
  }
  return response({ error: "Endpoint not found" }, 404);
}
