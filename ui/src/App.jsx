import React, { useEffect, useMemo, useRef, useState } from "react";

const API = "http://127.0.0.1:8000/api";

async function j(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(await res.text());
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

function NoteCard({ title, items, text }) {
  return (
    <section className="card">
      <h4>{title}</h4>
      {text != null ? <p>{text || "-"}</p> : null}
      {items ? <ul>{(items.length ? items : ["(none)"]).map((x, i) => <li key={i}>{x}</li>)}</ul> : null}
    </section>
  );
}

export function App() {
  const [meetings, setMeetings] = useState([]);
  const [selected, setSelected] = useState(null);
  const [meta, setMeta] = useState(null);
  const [transcript, setTranscript] = useState(null);
  const [notes, setNotes] = useState(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);

  const [sourcePath, setSourcePath] = useState("");
  const [runIdInput, setRunIdInput] = useState("");
  const [job, setJob] = useState(null);
  const pollRef = useRef(null);

  async function loadMeetings() {
    const data = await j(`${API}/meetings`);
    setMeetings(data);
    if (!selected && data.length) setSelected(data[0].run_id);
  }

  async function loadSelected(runId) {
    if (!runId) return;
    setLoading(true);
    try {
      const [m, t, n] = await Promise.all([
        j(`${API}/meetings/${runId}`),
        j(`${API}/meetings/${runId}/transcript`).catch(() => null),
        j(`${API}/meetings/${runId}/notes`).catch(() => null),
      ]);
      setMeta(m);
      setTranscript(t);
      setNotes(n);
    } finally {
      setLoading(false);
    }
  }

  async function pollJob(jobId) {
    try {
      const status = await j(`${API}/jobs/${jobId}`);
      setJob(status);
      if (status.status === "completed") {
        clearInterval(pollRef.current);
        pollRef.current = null;
        await loadMeetings();
        setSelected(status.run_id);
      }
      if (status.status === "failed") {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    } catch {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function startNewMeeting() {
    if (!sourcePath.trim()) return;
    const payload = {
      source_audio_path: sourcePath.trim(),
      run_id: runIdInput.trim() || null,
      config_dir: "configs",
      align: false,
    };
    const created = await j(`${API}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setJob(created);
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(() => pollJob(created.job_id), 2000);
    pollJob(created.job_id);
  }

  useEffect(() => {
    loadMeetings();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    loadSelected(selected);
  }, [selected]);

  const filteredSegments = useMemo(() => {
    const segs = transcript?.segments || [];
    if (!search.trim()) return segs;
    const q = search.toLowerCase();
    return segs.filter((s) => (s.text || "").toLowerCase().includes(q) || String(s.segment_id).includes(q));
  }, [transcript, search]);

  const noteData = notes?.notes || {};

  return (
    <div className="layout">
      <aside className="left">
        <h3>New Meeting</h3>
        <div className="newMeeting">
          <input placeholder="Absolute source path" value={sourcePath} onChange={(e) => setSourcePath(e.target.value)} />
          <input placeholder="Run ID (optional)" value={runIdInput} onChange={(e) => setRunIdInput(e.target.value)} />
          <button className="primary" onClick={startNewMeeting}>Run Meeting</button>
          {job ? <p className="muted">Job: {job.status} {job.run_id ? `(${job.run_id})` : ""}</p> : null}
        </div>

        <h3>Recent Meetings</h3>
        <ul className="list">
          {meetings.map((m) => (
            <li key={m.run_id}>
              <button className={m.run_id === selected ? "active" : ""} onClick={() => setSelected(m.run_id)}>{m.run_id}</button>
            </li>
          ))}
        </ul>
        <h3>Sources / Artifacts</h3>
        <div className="artifacts">
          {meta?.artifacts ? Object.entries(meta.artifacts).map(([stage, files]) => (
            <div key={stage}>
              <strong>{stage}</strong>
              <ul>{files.map((f) => <li key={f}>{f}</li>)}</ul>
            </div>
          )) : <p className="muted">No meeting selected.</p>}
        </div>
      </aside>

      <main className="center">
        <div className="toolbar">
          <input placeholder="Search transcript or ask (future chat)" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className="transcript">
          {loading ? <p className="muted">Loading...</p> : null}
          {!loading && !transcript ? <p className="muted">No transcript available for this run.</p> : null}
          {!loading && transcript && !filteredSegments.length ? <p className="muted">No matching segments.</p> : null}
          {!loading && filteredSegments.map((s, i) => (
            <div className="segment" key={`${s.segment_id}-${i}`}>
              <div className="time">{Number(s.span.start_sec).toFixed(2)}-{Number(s.span.end_sec).toFixed(2)}</div>
              <div className="speaker">{s.speaker_id || "Speaker"}</div>
              <div className="text">{s.text}</div>
            </div>
          ))}
        </div>
      </main>

      <aside className="right">
        <h3>Studio</h3>
        <div className="actions">
          <button onClick={async () => { if (!selected) return; await j(`${API}/meetings/${selected}/actions/rerun-summary`, { method: "POST" }); await loadSelected(selected); }}>Re-run Summary</button>
          <button onClick={async () => { if (!selected) return; const md = await j(`${API}/meetings/${selected}/export?format=markdown`); const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([md],{type:'text/markdown'})); a.download=`${selected}.md`; a.click(); }}>Export Markdown</button>
          <button onClick={async () => { if (!selected) return; const js = await j(`${API}/meetings/${selected}/export?format=json`); const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([JSON.stringify(js,null,2)],{type:'application/json'})); a.download=`${selected}.json`; a.click(); }}>Export JSON</button>
        </div>

        <h3>Notes</h3>
        <NoteCard title="Summary" text={noteData.summary || ""} />
        <NoteCard title="Decisions" items={noteData.decisions || []} />
        <NoteCard title="Action Items" items={noteData.action_items || []} />
        <NoteCard title="Open Questions" items={noteData.open_questions || []} />
        <NoteCard title="Risks" items={noteData.risks || []} />
      </aside>
    </div>
  );
}
