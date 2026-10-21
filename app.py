import html

import altair as alt
import pandas as pd
import streamlit as st

from cloudshield.config import get_settings
from cloudshield.db import Database
from cloudshield.service import BackupService
from cloudshield.storage import build_storage
from cloudshield.utils import human_size, sha256_bytes

st.set_page_config(page_title="CloudShield Backup", layout="wide")

INK, TEAL, AMBER, RED = "#0F1B33", "#0E8F82", "#E3A008", "#D64545"


@st.cache_resource
def get_service():
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(settings.db_path)
    return settings, db, BackupService(db=db, storage=build_storage(settings), settings=settings)


settings, db, service = get_service()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700&family=DM+Sans:wght@400;500;600&family=DM+Mono:wght@400;500&display=swap');
.stApp, .stApp p, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp td, .stApp th { font-family: 'DM Sans', sans-serif; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p.brand, .stApp p.ptitle, .stApp p.sect { font-family: 'Sora', sans-serif; letter-spacing: -0.01em; color: #0F1B33; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
.block-container { padding: 2rem 2.4rem 3rem; max-width: 1240px; }

section[data-testid="stSidebar"] { background: #0F1B33; width: 17rem !important; }
section[data-testid="stSidebar"] * { color: #C9D3E6; }
.stApp p.brand { font-size: 1.45rem; font-weight: 700; color: #fff !important; margin: .2rem 0 0 0; }
.stApp p.brand span { color: #3CC4B4 !important; }
.stApp p.tag { font-size: .82rem; color: #8494B2 !important; margin: 0 0 1.4rem 0; }
section[data-testid="stSidebar"] [role="radiogroup"] { gap: .15rem; }
section[data-testid="stSidebar"] [role="radiogroup"] label { padding: .55rem .8rem; border-radius: 5px; width: 100%; cursor: pointer; }
section[data-testid="stSidebar"] [role="radiogroup"] label:hover { background: #1A2A4A; }
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) { background: #16294D; box-shadow: inset 3px 0 0 #3CC4B4; }
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] > div > div:first-child { display: none; }
section[data-testid="stSidebar"] [role="radiogroup"] label p { font-weight: 500; font-size: .96rem; color: #E6ECF7 !important; }
.sbfoot { font-size: .84rem; line-height: 1.9; border-top: 1px solid #22345A; padding-top: .9rem; margin-top: 1.6rem; }
.dot { display:inline-block; width:.55rem; height:.55rem; border-radius:50%; margin-right:.5rem; }

.stApp p.ptitle { font-size: 1.8rem; font-weight: 600; margin: 0; line-height: 1.2; }
.stApp p.psub { color: #5E6C84; margin: .3rem 0 1.4rem 0; }
.stApp p.sect { font-size: 1.1rem; font-weight: 600; margin: 0 0 .6rem 0; }

[data-testid="stMetric"] { background:#fff; border:1px solid #DCE2EB; border-radius:8px; padding:1rem 1.1rem; }
[data-testid="stMetricLabel"] p { color:#5E6C84; font-size:.88rem; }
[data-testid="stMetricValue"] { font-family:'Sora', sans-serif; font-weight:600; }
[data-testid="stVerticalBlockBorderWrapper"] { background:#fff; border-radius:8px; border-color:#DCE2EB; }

.rmap { background:#fff; border:1px solid #DCE2EB; border-radius:8px; overflow:hidden; }
.rrow { display:grid; grid-template-columns: 2.2fr .5fr 1fr 1fr 1.3fr; gap:.8rem; align-items:center;
        padding:.6rem 1.1rem; border-top:1px solid #EEF1F6; font-size:.92rem; }
.rrow.head { border-top:0; background:#F4F6F9; color:#5E6C84; font-size:.82rem; font-weight:600; }
.rname { font-weight:500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.mono { font-family:'DM Mono', monospace; color:#5E6C84; font-size:.84rem; }
.cell { border-radius:4px; padding:.22rem 0; font-size:.8rem; font-weight:600; text-align:center; }
.cell.ok { background:#DDF3EF; color:#0A6B61; }
.cell.bad { background:#FBE0DF; color:#A32622; }
.hashbox { font-family:'DM Mono', monospace; background:#0F1B33; color:#BFE9E3; border-radius:6px;
           padding:.7rem .9rem; font-size:.84rem; word-break:break-all; margin:.3rem 0 .8rem 0; }
.stApp .stepno { font-family:'Sora', sans-serif; color:#0E8F82; font-weight:700; font-size:.85rem; margin:0; }
.stApp .steph { font-family:'Sora', sans-serif; font-weight:600; font-size:1.05rem; margin:0 0 .6rem 0; color:#0F1B33; }
.stButton > button[kind="primary"] { background:#0E8F82; border:0; border-radius:6px; font-weight:600; }
.stButton > button[kind="primary"]:hover { background:#0A6B61; }
.stButton > button, .stDownloadButton > button { border-radius:6px; }
@media (max-width: 760px) { .rrow { grid-template-columns: 2fr .5fr 1fr 1fr; } .rrow > :last-child { display:none; } }
</style>
""", unsafe_allow_html=True)


def page_header(title, sub):
    st.markdown(f'<p class="ptitle">{title}</p><p class="psub">{sub}</p>', unsafe_allow_html=True)


def cell(ok):
    return f'<div class="cell {"ok" if ok else "bad"}">{"OK" if ok else "BAD"}</div>'


files = db.list_files()
backups = db.list_backups(limit=10000)
health = service.health_summary()

with st.sidebar:
    st.markdown('<p class="brand">Cloud<span>Shield</span></p><p class="tag">Backup and recovery</p>', unsafe_allow_html=True)
    page = st.radio("Navigation", ["Overview", "Backup", "Versions", "Recovery", "Audit log"], label_visibility="collapsed")
    st.markdown(
        '<div class="sbfoot">' + "".join(
            f'<div><span class="dot" style="background:{TEAL if health[k] == "Available" else RED}"></span>{label} · {health[k].lower()}</div>'
            for k, label in (("replica_a", "Replica A"), ("replica_b", "Replica B"))) + "</div>",
        unsafe_allow_html=True)

# ------------------------------------------------------------------ overview
if page == "Overview":
    page_header("Overview", "Current state of every backed-up file and its replicas.")
    healthy = sum(1 for b in backups if b["status"] == "healthy")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Files", len(files))
    c2.metric("Versions", len(backups))
    c3.metric("Data protected", human_size(sum(b["size_bytes"] for b in backups)))
    c4.metric("Need attention", len(backups) - healthy)
    st.write("")

    if not backups:
        st.info("No backups yet. Use Backup to upload a file.")
    else:
        left, right = st.columns([3, 2], gap="large")
        with left:
            st.markdown('<p class="sect">Replica status</p>', unsafe_allow_html=True)
            rows = ['<div class="rmap"><div class="rrow head"><div>File</div><div>Ver.</div><div>Replica A</div>'
                    '<div>Replica B</div><div>SHA-256</div></div>']
            for b in backups[:10]:
                rows.append(
                    f'<div class="rrow"><div class="rname">{html.escape(b["filename"])}</div><div>v{b["version"]}</div>'
                    f'<div>{cell(b["replica_a_ok"])}</div><div>{cell(b["replica_b_ok"])}</div>'
                    f'<div class="mono">{b["sha256"][:12]}…</div></div>')
            st.markdown("".join(rows) + "</div>", unsafe_allow_html=True)
            st.write("")
            st.caption("Reflects the last scan or repair. Run a scan on the Recovery page to refresh it.")
        with right:
            st.markdown('<p class="sect">Version health</p>', unsafe_allow_html=True)
            counts = pd.DataFrame({"Status": ["healthy", "degraded", "unavailable"],
                                   "Versions": [sum(1 for b in backups if b["status"] == s)
                                                for s in ("healthy", "degraded", "unavailable")]})
            donut = alt.Chart(counts).mark_arc(innerRadius=62, outerRadius=100).encode(
                theta="Versions:Q",
                color=alt.Color("Status:N", scale=alt.Scale(domain=["healthy", "degraded", "unavailable"],
                                                           range=[TEAL, AMBER, RED]),
                                legend=alt.Legend(orient="bottom", title=None)),
                tooltip=["Status", "Versions"]).properties(height=250)
            st.altair_chart(donut, width="stretch")

        st.markdown('<p class="sect">Storage by file</p>', unsafe_allow_html=True)
        sizes = {}
        for b in backups:
            sizes[b["filename"]] = sizes.get(b["filename"], 0) + b["size_bytes"]
        sdf = pd.DataFrame({"File": list(sizes), "Bytes": list(sizes.values())})
        bars = alt.Chart(sdf).mark_bar(color=TEAL, cornerRadiusEnd=3, size=18).encode(
            x=alt.X("Bytes:Q", title="Total bytes across versions"), y=alt.Y("File:N", sort="-x", title=None),
            tooltip=["File", "Bytes"]).properties(height=alt.Step(34))
        st.altair_chart(bars, width="stretch")

        with st.expander("Replica locations"):
            st.code(f"Replica A: {settings.replica_a_dir}\nReplica B: {settings.replica_b_dir}", language="text")

# ------------------------------------------------------------------ backup
elif page == "Backup":
    page_header("Backup", "Each upload becomes a new version stored on both replicas with a SHA-256 checksum.")
    with st.container(border=True):
        uploads = st.file_uploader("Files", accept_multiple_files=True)
        note = st.text_input("Version note", placeholder="Optional")
        go = st.button("Back up", type="primary", disabled=not uploads)
    if uploads and go:
        for up in uploads:
            data = up.getvalue()
            existing = db.list_versions(up.name)
            if existing and existing[0]["sha256"] == sha256_bytes(data):
                st.info(f"{up.name} is identical to version {existing[0]['version']}; nothing new to back up.")
                continue
            try:
                r = service.create_backup(up.name, data, note.strip())
            except Exception as exc:
                st.error(f"{up.name}: {exc}")
                continue
            st.success(f"{r['filename']} saved as version {r['version']} ({human_size(r['size_bytes'])})")
            st.markdown(f'<div class="hashbox">{r["sha256"]}</div>', unsafe_allow_html=True)
            if not (r["replica_a_ok"] and r["replica_b_ok"]):
                st.warning("One replica write failed. This version is degraded; run Repair on the Recovery page.")

# ------------------------------------------------------------------ versions
elif page == "Versions":
    page_header("Versions", "Version history for each file, with download from a verified replica.")
    if not files:
        st.info("No backups yet.")
    else:
        chosen = st.selectbox("File", [f["filename"] for f in files])
        versions = db.list_versions(chosen)
        st.dataframe(pd.DataFrame([{
            "Version": v["version"], "Created (UTC)": v["created_at"].replace("T", " ")[:19],
            "Size": human_size(v["size_bytes"]), "Status": v["status"], "Note": v["note"] or "",
            "SHA-256": v["sha256"][:16] + "…"} for v in versions]), width="stretch", hide_index=True)
        labels = {f"Version {v['version']} · {v['created_at'].replace('T', ' ')[:19]}": v for v in versions}
        pick = labels[st.selectbox("Download version", list(labels))]
        try:
            st.download_button("Download", data=service.read_valid_replica(pick["id"], audit=False),
                               file_name=chosen, mime="application/octet-stream", type="primary",
                               on_click=service.log_download, args=(pick["id"],))
        except Exception as exc:
            st.error(f"No valid replica could be read: {exc}")

# ------------------------------------------------------------------ recovery
elif page == "Recovery":
    page_header("Recovery", "Inject a failure, verify every replica, then repair from a good copy.")
    s1, s2, s3 = st.columns(3, gap="medium")
    with s1, st.container(border=True):
        st.markdown('<p class="stepno">STEP 1</p><p class="steph">Inject failure</p>', unsafe_allow_html=True)
        if not backups:
            st.caption("Back up a file first.")
        elif not settings.allow_failure_simulation:
            st.caption("Failure simulation is disabled.")
        else:
            smap = {f"{b['filename']} · v{b['version']}": b for b in backups}
            target = smap[st.selectbox("Version", list(smap))]
            rep = st.radio("Replica", ["A", "B"], horizontal=True)
            act = st.radio("Failure", ["Corrupt content", "Delete replica"], horizontal=True)
            if st.button("Inject"):
                try:
                    service.simulate_failure(target["id"], rep, act)
                    st.session_state.pop("scan_results", None)
                    st.warning(f"{act} applied to replica {rep}.")
                except Exception as exc:
                    st.error(str(exc))
    with s2, st.container(border=True):
        st.markdown('<p class="stepno">STEP 2</p><p class="steph">Verify</p>', unsafe_allow_html=True)
        st.caption("Re-hash every replica and compare with the stored checksum.")
        if st.button("Run integrity scan", type="primary"):
            with st.spinner("Hashing replicas"):
                st.session_state["scan_results"] = service.scan_all()
            st.session_state.pop("repair", None)
            st.rerun()
    with s3, st.container(border=True):
        st.markdown('<p class="stepno">STEP 3</p><p class="steph">Repair</p>', unsafe_allow_html=True)
        st.caption("Rewrite missing or corrupted replicas from a verified copy.")
        if st.button("Repair replicas", type="primary"):
            repairs, lost = service.repair_all()
            st.session_state["repair"] = {"repairs": repairs, "lost": len(lost)}
            st.session_state.pop("scan_results", None)
            st.rerun()

    st.write("")
    rep_state = st.session_state.get("repair")
    if rep_state:
        if rep_state["repairs"]:
            m1, m2, m3 = st.columns(3)
            m1.metric("Versions repaired", len(rep_state["repairs"]))
            m2.metric("Replicas rewritten", sum(len(r["repaired"]) for r in rep_state["repairs"]))
            m3.metric("Recovery time", f"{sum(r['ms'] for r in rep_state['repairs']):.1f} ms")
            st.success("Repair complete. Run the integrity scan again to confirm all hashes match.")
        else:
            st.info("No replica needed repair.")
        if rep_state["lost"]:
            st.error(f"{rep_state['lost']} version(s) have no valid replica left and cannot be recovered.")

    results = st.session_state.get("scan_results")
    if results is not None:
        bad = [r for r in results if r["result"] != "OK"]
        (st.warning if bad else st.success)(
            f"{len(bad)} of {len(results)} replica checks failed." if bad else f"All {len(results)} replica checks passed.")
        st.dataframe(pd.DataFrame(results).rename(columns={
            "backup_id": "ID", "filename": "File", "version": "Ver.", "replica": "Replica", "result": "Result",
            "expected_hash": "Expected", "actual_hash": "Actual"}), width="stretch", hide_index=True)

# ------------------------------------------------------------------ audit
else:
    page_header("Audit log", "Every backup, scan, failure, repair and download is recorded.")
    logs = db.list_audit(limit=500)
    if logs:
        df = pd.DataFrame(logs)
        st.dataframe(df, width="stretch", hide_index=True)
        st.download_button("Export CSV", df.to_csv(index=False).encode(), "cloudshield_audit.csv", "text/csv")
    else:
        st.info("No events yet.")
