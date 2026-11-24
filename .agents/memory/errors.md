# Engineering Failure & Self-Healing Log (`.agents/memory/errors.md`)

> Rule: Cap automated retry loops at **3 attempts**. Log root cause, deterministic fix, and regression test here so future sessions never repeat the mistake.

1. **`ERR_CONNECTION_REFUSED` on `localhost:8088` in Windows Microsoft Edge**:
   - **Root Cause**: Legacy `.bat` only bound IPv4 `127.0.0.1:8080`, missed IPv6 `[::1]:8088`, and launched browser before `/api/v1/health` returned `200 OK`.
   - **Fix**: `tools/run_local_server.py` binds dual-stack (`127.0.0.1` + `::1`) on both `8088` and `8080`, polls `/api/v1/health`, and pairs with serverless `gh-pages` fallback (`hadeeth_serverless_engine.js`).
2. **Third-Party Browser CORS on `search.hadeeth.com`**:
   - **Root Cause**: Upstream `search.hadeeth.com` omits `Access-Control-Allow-Origin: *` for `*.github.io`.
   - **Fix**: Compiled 48,911 bilingual Hadiths + 283,601 Rekhta lexicon entries into compressed `.bin` shards in `gh-pages` decoded via `DecompressionStream("gzip")`.
