import html
import pandas as pd
import streamlit as st

from cloudshield.config import get_settings
from cloudshield.db import Database
from cloudshield.service import BackupService
from cloudshield.storage import build_storage
from cloudshield.utils import human_size

st.set_page_config(page_title="CloudShield Backup", page_icon="🛡️", layout="wide",
                   initial_sidebar_state="collapsed")


@st.cache_resource
def get_service():
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(settings.db_path)
    return settings, db, BackupService(db=db, storage=build_storage(settings), settings=settings)


settings, db, service = get_service()

# ------------------------------------------------------------------ styling
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
html, body, [class*="st-"], .stApp { font-family: 'IBM Plex Sans', sans-serif; }
h1, h2, h3, .cs-title { font-family: 'Space Grotesk', sans-serif !important; letter-spacing: -0.01em; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
.block-container { padding-top: 1.2rem; max-width: 1280px; }

.cs-hero { background: #14213A; color: #F5F7FA; border-radius: 6px; padding: 1.6rem 1.8rem;
  display: flex; justify-content: space-between; align-items: flex-end; gap: 2rem; flex-wrap: wrap; }
.cs-title { font-size: 2.3rem; font-weight: 700; margin: 0; line-height: 1.05; }
.cs-sub { color: #AAB8D0; margin: .5rem 0 0 0; max-width: 34rem; }
.cs-live { text-align: right; font-size: .9rem; color: #AAB8D0; line-height: 1.5; }
.cs-live b { color: #fff; font-weight: 600; }
.cs-dot { display:inline-block; width:.6rem; height:.6rem; border-radius:50%; margin-right:.4rem; }

[data-testid="stMetric"] { background: #fff; border: 1px solid #D5DCE6; border-radius: 6px; padding: .9rem 1rem; }
[data-testid="stMetricLabel"] p { color: #5B6B84; font-size: .9rem; }
[data-testid="stMetricValue"] { font-family: 'Space Grotesk', sans-serif; }

.stTabs [data-baseweb="tab-list"] { gap: 1.6rem; border-bottom: 1px solid #D5DCE6; }
.stTabs [data-baseweb="tab"] { height: 2.8rem; padding: 0; font-weight: 500; }

/* replica map: the one signature element */
.rmap { background:#fff; border:1px solid #D5DCE6; border-radius:6px; overflow:hidden; }
.rrow { display:grid; grid-template-columns: 2.4fr .5fr 1.1fr 1.1fr 1.3fr; align-items:center;
  gap:.8rem; padding:.55rem 1rem; border-top:1px solid #EDF1F6; font-size:.93rem; }
.rrow.head { border-top:0; background:#F0F3F8; color:#5B6B84; font-size:.85rem; font-weight:500; }
.rname { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-weight:500; }
.rhash { font-family:'IBM Plex Mono', monospace; color:#5B6B84; font-size:.85rem; }
.cell { border-radius:3px; padding:.25rem .6rem; font-size:.85rem; font-weight:600; text-align:center; }
.cell.ok  { background:#DDF3EF; color:#0A6B61; }
.cell.bad { background:#FBE0DF; color:#A32622; }
.pill { display:inline-block; border-radius:3px; padding:.1rem .55rem; font-size:.82rem; font-weight:600; }
.pill.healthy { background:#DDF3EF; color:#0A6B61; }
.pill.degraded { background:#FFF0C7; color:#7A5600; }
.pill.unavailable { background:#FBE0DF; color:#A32622; }
.hashbox { font-family:'IBM Plex Mono', monospace; background:#14213A; color:#BFE9E3; border-radius:6px;
  padding:.7rem .9rem; font-size:.85rem; word-break:break-all; }
.step { border-left: 3px solid #0E8F82; padding-left: .8rem; margin-bottom: .4rem; }
.step h4 { margin: 0; font-family:'Space Grotesk', sans-serif; }
.step p { margin: .15rem 0 0 0; color:#5B6B84; font-size:.92rem; }
.stButton > button[kind="primary"] { background:#0E8F82; border:0; border-radius:4px; font-weight:600; }
.stButton > button[kind="primary"]:hover { background:#0A6B61; }
@media (max-width: 760px) { .rrow { grid-template-columns: 2fr .5fr 1fr 1fr; } .rrow > :last-child { display:none; } }
</style>
""", unsafe_allow_html=True)


def pill(status):
    return f'<span class="pill {status}">{html.escape(status)}</span>'


# ------------------------------------------------------------------ data
files = db.list_files()
backups = db.list_backups(limit=10000)
n_ok = sum(1 for b in backups if b["status"] == "healthy")
n_attn = len(backups) - n_ok
health = service.health_summary()
online = all(v == "Available" for v in health.values())
dot = "#0E8F82" if online else "#D64545"
total_bytes = sum(b["size_bytes"] for b in backups)

st.markdown(f"""
<div class="cs-hero">
  <div>
    <p class="cs-title">CloudShield Backup</p>
    <p class="cs-sub">Every upload is hashed, written to two independent replicas, versioned, and
    can be verified and repaired at any time.</p>
  </div>
  <div class="cs-live">
    <span class="cs-dot" style="background:{dot}"></span><b>{'Both replicas online' if online else 'Replica offline'}</b><br>
    {len(files)} files · {len(backups)} versions · {human_size(total_bytes)} protected
  </div>
</div>
""", unsafe_allow_html=True)
st.write("")

tab_dash, tab_backup, tab_versions, tab_lab, tab_audit = st.tabs(
    ["Dashboard", "Back up files", "Versions", "Recovery lab", "Audit log"])

# ------------------------------------------------------------------ dashboard
with tab_dash:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tracked files", len(files))
    c2.metric("Backup versions", len(backups))
    c3.metric("Fully replicated", n_ok)
    c4.metric("Need attention", n_attn)

    st.subheader("Replica map")
    st.caption("Latest versions and the verified state of each replica (updated by every scan and repair).")
    if backups:
        rows = ['<div class="rmap"><div class="rrow head"><div>File</div><div>Ver.</div>'
                '<div>Replica A</div><div>Replica B</div><div>SHA-256</div></div>']
        for b in backups[:12]:
            ca = ("ok", "OK") if b["replica_a_ok"] else ("bad", "BAD")
            cb = ("ok", "OK") if b["replica_b_ok"] else ("bad", "BAD")
            rows.append(
                f'<div class="rrow"><div class="rname">{html.escape(b["filename"])}</div><div>v{b["version"]}</div>'
                f'<div><div class="cell {ca[0]}">{ca[1]}</div></div><div><div class="cell {cb[0]}">{cb[1]}</div></div>'
                f'<div class="rhash">{b["sha256"][:12]}…</div></div>')
        rows.append("</div>")
        st.markdown("".join(rows), unsafe_allow_html=True)
        st.write("")
        left, right = st.columns([3, 2])
        with left:
            st.subheader("Protected data by file")
            sizes = {}
            for b in backups:
                sizes[b["filename"]] = sizes.get(b["filename"], 0) + b["size_bytes"]
            st.bar_chart(pd.Series(sizes, name="Bytes"), color="#0E8F82", horizontal=True)
        with right:
            st.subheader("Replica locations")
            st.markdown(f"**Replica A** · {health['replica_a']}")
            st.code(str(settings.replica_a_dir), language="text")
            st.markdown(f"**Replica B** · {health['replica_b']}")
            st.code(str(settings.replica_b_dir), language="text")
    else:
        st.info("No backups yet. Open **Back up files** and upload something to get started.")

# ------------------------------------------------------------------ backup
with tab_backup:
    st.subheader("Create backup versions")
    st.write("Each file gets a new version number, a SHA-256 checksum, and one copy on each replica.")
    uploads = st.file_uploader("Choose one or more files", accept_multiple_files=True)
    note = st.text_input("Version note (optional)", placeholder="e.g. Report before submission")
    if uploads and st.button("Back up now", type="primary"):
        for up in uploads:
            try:
                r = service.create_backup(up.name, up.getvalue(), note.strip())
                st.success(f"{r['filename']} stored as version {r['version']} · {human_size(r['size_bytes'])}")
                st.markdown(f'<div class="hashbox">{r["sha256"]}</div>', unsafe_allow_html=True)
                if not (r["replica_a_ok"] and r["replica_b_ok"]):
                    st.warning("One replica write failed, so this version is degraded. See the audit log.")
            except Exception as exc:
                st.error(f"{up.name}: {exc}")
        st.caption("Switch to the Dashboard tab to see the updated replica map.")

# ------------------------------------------------------------------ versions
with tab_versions:
    st.subheader("Version history and download")
    if not files:
        st.info("Nothing backed up yet.")
    else:
        chosen = st.selectbox("File", [f["filename"] for f in files])
        versions = db.list_versions(chosen)
        st.dataframe(pd.DataFrame([{
            "Version": v["version"], "Created (UTC)": v["created_at"], "Size": human_size(v["size_bytes"]),
            "Status": v["status"], "Note": v["note"] or "", "SHA-256": v["sha256"][:20] + "…"} for v in versions]),
            width="stretch", hide_index=True)
        vmap = {f"v{v['version']} · {v['created_at']} · {v['status']}": v for v in versions}
        pick = vmap[st.selectbox("Version", list(vmap))]
        try:
            st.download_button("Download this version", data=service.read_valid_replica(pick["id"]),
                               file_name=chosen, mime="application/octet-stream")
        except Exception as exc:
            st.error(f"No valid replica could be read: {exc}")

# ------------------------------------------------------------------ recovery lab
with tab_lab:
    st.subheader("Recovery lab")
    st.write("Break a replica on purpose, detect the damage, then repair it. This is the demo sequence for your instructor.")

    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown('<div class="step"><h4>1. Break a replica</h4><p>Corrupt or delete one stored copy.</p></div>', unsafe_allow_html=True)
        if not backups:
            st.info("Back up a file first.")
        elif not settings.allow_failure_simulation:
            st.info("Failure simulation is disabled.")
        else:
            smap = {f"{b['filename']} · v{b['version']}": b for b in backups}
            target = smap[st.selectbox("Version", list(smap), key="sim_v")]
            rep = st.radio("Replica", ["A", "B"], horizontal=True)
            act = st.radio("Failure", ["Corrupt content", "Delete replica"], horizontal=True)
            if st.button("Inject failure"):
                try:
                    service.simulate_failure(target["id"], rep, act)
                    st.session_state.pop("scan_results", None)
                    st.warning(f"{act} applied to replica {rep}.")
                except Exception as exc:
                    st.error(str(exc))
    with s2:
        st.markdown('<div class="step"><h4>2. Detect</h4><p>Re-hash every replica and compare with the stored checksum.</p></div>', unsafe_allow_html=True)
        if st.button("Run integrity scan", type="primary"):
            with st.spinner("Hashing replicas…"):
                st.session_state["scan_results"] = service.scan_all()
            st.rerun()
    with s3:
        st.markdown('<div class="step"><h4>3. Repair</h4><p>Rewrite bad replicas from a verified copy.</p></div>', unsafe_allow_html=True)
        if st.button("Repair all replicas", type="primary"):
            repairs, lost = service.repair_all()
            st.session_state["repair"] = {"repairs": repairs, "lost": len(lost)}
            st.session_state.pop("scan_results", None)
            st.rerun()

    st.divider()
    rep_state = st.session_state.get("repair")
    if rep_state:
        if rep_state["repairs"]:
            total_ms = sum(r["ms"] for r in rep_state["repairs"])
            m1, m2, m3 = st.columns(3)
            m1.metric("Versions repaired", len(rep_state["repairs"]))
            m2.metric("Replicas rewritten", sum(len(r["repaired"]) for r in rep_state["repairs"]))
            m3.metric("Recovery time", f"{total_ms:.1f} ms")
            st.success("Repair finished. Run another integrity scan to confirm every hash matches again.")
        else:
            st.info("Nothing needed repair.")
        if rep_state["lost"]:
            st.error(f"{rep_state['lost']} version(s) have no valid replica left and cannot be recovered.")

    results = st.session_state.get("scan_results")
    if results is not None:
        bad = [r for r in results if r["result"] != "OK"]
        st.markdown("#### Scan result")
        (st.warning if bad else st.success)(
            f"{len(bad)} of {len(results)} replica checks failed." if bad else f"All {len(results)} replica checks passed.")
        st.dataframe(pd.DataFrame(results).rename(columns={
            "backup_id": "ID", "filename": "File", "version": "Ver.", "replica": "Replica", "result": "Result",
            "expected_hash": "Expected", "actual_hash": "Actual"}), width="stretch", hide_index=True)

# ------------------------------------------------------------------ audit
with tab_audit:
    st.subheader("Audit log")
    logs = db.list_audit(limit=500)
    if logs:
        df = pd.DataFrame(logs)
        st.dataframe(df, width="stretch", hide_index=True)
        st.download_button("Download as CSV", df.to_csv(index=False).encode(), "cloudshield_audit.csv", "text/csv")
    else:
        st.info("No events yet.")
    with st.expander("About this prototype"):
        st.markdown("""
CloudShield stores two copies of every file version in separate directories and records metadata in
SQLite (part of Python, no external database). Integrity uses SHA-256. If both replicas sit on one
machine they demonstrate replica logic but not protection against physical disk loss; in the Colab
notebook, replica B can live on Google Drive so the two copies are on different storage.
""")
