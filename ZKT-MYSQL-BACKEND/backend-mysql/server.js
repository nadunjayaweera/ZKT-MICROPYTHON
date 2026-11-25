"use strict";
const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const mysql = require("mysql2/promise");

const envPath = path.join(__dirname, ".env");
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const m = /^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$/.exec(line);
    if (m && !Object.hasOwn(process.env, m[1]))
      process.env[m[1]] = m[2].replace(/^(['"])(.*)\1$/, "$2");
  }
}
const TOKEN = process.env.DEVICE_API_KEY;
if (
  !TOKEN ||
  TOKEN.length < 16 ||
  TOKEN === "replace-with-a-long-random-secret"
)
  throw Error("Set DEVICE_API_KEY (minimum 16 characters) in .env");
if (!process.env.DATABASE_URL) throw Error("Set DATABASE_URL in .env");
const PORT = Number(process.env.PORT || 3000);
const MAX_REQUEST_BYTES = 262144; // Safety cap for Node; ESP32 self-limits by heap.
const parsed = new URL(process.env.DATABASE_URL);
if (parsed.protocol !== "mysql:")
  throw Error("DATABASE_URL must start with mysql://");
const pool = mysql.createPool({
  host: parsed.hostname,
  port: Number(parsed.port || 3306),
  user: decodeURIComponent(parsed.username),
  password: decodeURIComponent(parsed.password),
  database: decodeURIComponent(parsed.pathname.slice(1)),
  waitForConnections: true,
  connectionLimit: Number(process.env.DB_CONNECTION_LIMIT || 5),
  decimalNumbers: false,
  timezone: "Z",
  enableKeepAlive: true,
});
function isDevice(s) {
  return typeof s === "string" && /^[A-Za-z0-9_-]{1,64}$/.test(s);
}
function indexOf(cursor) {
  if (cursor === null) return 0;
  if (typeof cursor !== "string") return null;
  const match = /^(\d+)\.([a-fA-F0-9]{80})$/.exec(cursor);
  if (!match) return null;
  const idx = Number(match[1]);
  return Number.isSafeInteger(idx) && idx > 0 ? idx : null;
}
function validateBatch(b) {
  if (!b || !isDevice(b.device_id)) return false;
  const start = indexOf(b.cursor),
    end = indexOf(b.next_cursor);
  if (
    start === null ||
    end === null ||
    !Array.isArray(b.records) ||
    b.records.length < 1 ||
    end - start !== b.records.length
  )
    return false;
  return b.records.every(
    (r) =>
      r &&
      Number.isSafeInteger(r.user_sn) &&
      r.user_sn >= 0 &&
      typeof r.device_user_id === "string" &&
      r.device_user_id.length <= 64 &&
      typeof r.record_time === "string" &&
      r.record_time.length <= 32 &&
      (r.validation_status === undefined ||
        ["VALID", "INVALID"].includes(r.validation_status)) &&
      (r.raw_hex === undefined ||
        (typeof r.raw_hex === "string" &&
          /^[0-9a-fA-F]{80}$/.test(r.raw_hex))) &&
      (r.ip === undefined || (typeof r.ip === "string" && r.ip.length <= 100)),
  );
}
function send(res, status, obj) {
  const body = Buffer.from(JSON.stringify(obj));
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Content-Length": body.length,
    "Cache-Control": "no-store",
  });
  res.end(body);
}
function auth(req) {
  return req.headers.authorization === "Bearer " + TOKEN;
}
function readBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const pieces = [];
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > MAX_REQUEST_BYTES) {
        reject(Object.assign(Error("Body too large"), { status: 413 }));
        req.destroy();
      } else pieces.push(chunk);
    });
    req.on("end", () => {
      try {
        resolve(JSON.parse(Buffer.concat(pieces).toString("utf8")));
      } catch (_) {
        reject(Object.assign(Error("Invalid JSON"), { status: 400 }));
      }
    });
    req.on("error", reject);
  });
}
async function savedFor(device) {
  const [rows] = await pool.execute(
    "SELECT committed_cursor, total_saved FROM zkt_sync_devices WHERE device_id=?",
    [device],
  );
  return rows.length
    ? { cursor: rows[0].committed_cursor, count: Number(rows[0].total_saved) }
    : { cursor: null, count: 0 };
}
async function commitBatch(batch) {
  const conn = await pool.getConnection();
  try {
    await conn.beginTransaction();
    await conn.execute(
      "INSERT IGNORE INTO zkt_sync_devices (device_id) VALUES (?)",
      [batch.device_id],
    );
    const [rows] = await conn.execute(
      "SELECT committed_cursor, total_saved FROM zkt_sync_devices WHERE device_id=? FOR UPDATE",
      [batch.device_id],
    );
    const saved = rows[0];
    if (saved.committed_cursor === batch.next_cursor) {
      await conn.commit();
      return {
        status: 200,
        body: {
          success: true,
          replay: true,
          inserted: 0,
          committed_cursor: saved.committed_cursor,
        },
      };
    }
    if (saved.committed_cursor !== batch.cursor) {
      await conn.commit();
      return {
        status: 409,
        body: {
          success: false,
          error: "CURSOR_MISMATCH",
          committed_cursor: saved.committed_cursor,
        },
      };
    }
    const start = indexOf(batch.cursor);
    for (let i = 0; i < batch.records.length; i++) {
      const r = batch.records[i];
      await conn.execute(
        `INSERT INTO zkt_attendance_records
        (device_id, record_index, user_sn, device_user_id, record_time, device_ip, raw_record)
        VALUES (?,?,?,?,?,?,?)`,
        [
          batch.device_id,
          start + i + 1,
          r.user_sn,
          r.device_user_id,
          r.record_time,
          r.ip || null,
          JSON.stringify(r),
        ],
      );
    }
    await conn.execute(
      "UPDATE zkt_sync_devices SET committed_cursor=?, total_saved=total_saved+? WHERE device_id=?",
      [batch.next_cursor, batch.records.length, batch.device_id],
    );
    await conn.commit();
    console.log(
      "Committed",
      batch.records.length,
      "records from",
      batch.device_id,
    );
    return {
      status: 200,
      body: {
        success: true,
        inserted: batch.records.length,
        committed_cursor: batch.next_cursor,
      },
    };
  } catch (e) {
    try {
      await conn.rollback();
    } catch (_) {}
    throw e;
  } finally {
    conn.release();
  }
}
async function handle(req, res) {
  const url = new URL(req.url, "http://localhost");
  if (req.method === "GET" && url.pathname === "/health") {
    try {
      await pool.query("SELECT 1");
      return send(res, 200, {
        success: true,
        storage: "ok",
        database: "mysql",
      });
    } catch (e) {
      console.error("Database health check failed:", e.code || e.message);
      return send(res, 503, {
        success: false,
        storage: "unhealthy",
        database: "mysql",
      });
    }
  }
  if (!url.pathname.startsWith("/api/attendance/"))
    return send(res, 404, { success: false, error: "NOT_FOUND" });
  if (!auth(req))
    return send(res, 401, { success: false, error: "UNAUTHORIZED" });
  if (req.method === "GET" && url.pathname === "/api/attendance/sync-state") {
    const device = url.searchParams.get("device_id");
    if (!isDevice(device))
      return send(res, 400, { success: false, error: "BAD_DEVICE" });
    const saved = await savedFor(device);
    return send(res, 200, {
      success: true,
      cursor: saved.cursor,
      total_saved: saved.count,
    });
  }
  if (req.method === "POST" && url.pathname === "/api/attendance/batches") {
    const batch = await readBody(req);
    if (!validateBatch(batch))
      return send(res, 400, { success: false, error: "INVALID_BATCH" });
    const result = await commitBatch(batch);
    return send(res, result.status, result.body);
  }
  if (req.method === "GET" && url.pathname === "/api/attendance/records") {
    const device = url.searchParams.get("device_id");
    if (!isDevice(device))
      return send(res, 400, { success: false, error: "BAD_DEVICE" });
    const offset = Number(url.searchParams.get("offset") || "0");
    const limit = Number(url.searchParams.get("limit") || "20");
    if (
      !Number.isSafeInteger(offset) ||
      offset < 0 ||
      !Number.isSafeInteger(limit) ||
      limit < 1 ||
      limit > 100
    )
      return send(res, 400, { success: false, error: "BAD_PAGINATION" });
    const [rows] = await pool.execute(
      `SELECT raw_record FROM zkt_attendance_records WHERE device_id=? ORDER BY record_index ASC LIMIT ? OFFSET ?`,
      [device, limit, offset],
    );
    const records = rows.map((row) =>
      typeof row.raw_record === "string"
        ? JSON.parse(row.raw_record)
        : row.raw_record,
    );
    const saved = await savedFor(device);
    return send(res, 200, {
      success: true,
      records,
      count: records.length,
      offset,
      total_saved: saved.count,
    });
  }
  return send(res, 404, { success: false, error: "NOT_FOUND" });
}
const server = http.createServer((req, res) => {
  handle(req, res).catch((err) => {
    console.error("Request error:", err.code || err.message);
    if (!res.headersSent)
      send(res, err.status || 500, {
        success: false,
        error: err.status === 400 ? "INVALID_JSON" : "SERVER_ERROR",
      });
  });
});
async function start() {
  const conn = await pool.getConnection();
  try {
    const [rows] = await conn.query(
      `SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name IN ('zkt_sync_devices','zkt_attendance_records')`,
    );
    if (rows[0].n !== 2)
      throw Error("Missing MySQL tables. Run schema.sql first.");
  } finally {
    conn.release();
  }
  server.listen(PORT, "0.0.0.0", () =>
    console.log("ZKT MySQL backend listening on port", PORT),
  );
}
if (require.main === module)
  start().catch((e) => {
    console.error("Startup failed:", e.code || e.message);
    process.exitCode = 1;
    pool.end();
  });
module.exports = { server, pool, indexOf, validateBatch, commitBatch };
