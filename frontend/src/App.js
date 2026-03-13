import { useState, useRef, useEffect, useCallback } from "react";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:5051";

// ─── THEME ───────────────────────────────────────────────────────────────────
const T = {
  bg:          "#040d1a",
  surface:     "#071428",
  surfaceHigh: "#0a1e3d",
  border:      "rgba(99,160,255,0.12)",
  borderGlow:  "rgba(99,160,255,0.30)",
  accent:      "#3a8fff",
  accentDim:   "rgba(58,143,255,0.06)",
  accentMid:   "rgba(58,143,255,0.18)",
  text:        "#c8dcf5",
  textMuted:   "#6a90b8",
  textDim:     "#3a5878",
  success:     "#2ecc8c",
  warn:        "#f5a623",
  error:       "#f87171",
  salt:        "rgba(58,143,255,0.04)",
  accent2:     "#63c6ff",
};

const GENE_EXAMPLES = [
  "ectoine", "betaine", "compatible solute", "osmoprotectant",
  "catalase", "superoxide dismutase", "halotolerance",
  "cellulose synthase", "alginate", "exopolysaccharide",
  "lipase", "protease", "amylase",
];

// ─── STYLES ──────────────────────────────────────────────────────────────────
const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&family=DM+Sans:wght@300;400;500;600&display=swap');
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

@keyframes spin     { to { transform: rotate(360deg); } }
@keyframes fadeUp   { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
@keyframes pulse    { 0%,100%{opacity:1} 50%{opacity:0.3} }
@keyframes blink    { 0%,100%{opacity:1} 49%{opacity:1} 50%,99%{opacity:0} }
@keyframes scanH    { 0%{transform:translateX(-100%)} 100%{transform:translateX(100vw)} }
@keyframes glow     { 0%,100%{opacity:0.5} 50%{opacity:1} }

body {
  font-family: 'DM Sans', sans-serif;
  background: ${T.bg};
  color: ${T.text};
  min-height: 100vh;
  overflow-x: hidden;
}

.salt-bg {
  position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background:
    radial-gradient(ellipse 80% 60% at 50% -10%, rgba(58,143,255,0.08) 0%, transparent 70%),
    radial-gradient(ellipse 40% 40% at 80% 80%, rgba(99,198,255,0.04) 0%, transparent 60%);
}
.salt-crystals {
  position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background-image:
    linear-gradient(rgba(58,143,255,0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(58,143,255,0.025) 1px, transparent 1px);
  background-size: 52px 52px;
}
.scan-line {
  position: fixed; top: 0; height: 1px; left: 0; right: 0;
  background: linear-gradient(90deg, transparent 0%, ${T.accent2} 50%, transparent 100%);
  opacity: 0.12; pointer-events: none; z-index: 1;
  animation: scanH 7s linear infinite;
}

.app { min-height:100vh; display:flex; flex-direction:column; align-items:center; padding:0 0 100px; position:relative; }
.container { width:100%; max-width:900px; position:relative; z-index:2; padding: 0 24px; }

/* Header */
.header-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 24px 40px; margin-bottom: 0; width: 100%;
  border-bottom: 0.5px solid ${T.border};
  position: relative; z-index: 10;
}
.logo-wrap {
  display: inline-flex; align-items: baseline; gap: 10px;
}
.logo-text {
  font-family: 'Space Mono', monospace; font-size: 17px; font-weight: 700;
  color: ${T.accent2}; letter-spacing: -0.3px;
}
.logo-sub {
  font-size: 11px; color: ${T.textDim}; letter-spacing: 0.12em; text-transform: uppercase; font-weight: 500;
}
.header-pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 12px; border: 0.5px solid ${T.borderGlow}; border-radius: 100px;
  font-size: 11px; color: ${T.accent2}; font-family: 'Space Mono', monospace;
}
.header-pill-dot { width: 5px; height: 5px; border-radius: 50%; background: ${T.success}; display: inline-block; }

/* Hero */
.hero {
  padding: 56px 40px 40px; text-align: center; max-width: 900px; margin: 0 auto;
}
.hero-eyebrow {
  font-family: 'Space Mono', monospace; font-size: 11px; color: ${T.textDim};
  letter-spacing: 0.14em; text-transform: uppercase; margin-bottom: 18px;
}
.hero-title {
  font-family: 'Space Mono', monospace; font-size: clamp(32px,5vw,48px); font-weight: 700;
  color: #e8f4ff; line-height: 1.1; letter-spacing: -1px; margin-bottom: 14px;
}
.hero-title span { color: ${T.accent2}; }
.hero-desc {
  font-size: 15px; color: ${T.textMuted}; line-height: 1.75; max-width: 500px;
  margin: 0 auto 36px; font-weight: 300;
}

/* Search */
.search-outer { max-width: 620px; margin: 0 auto; }
.tags-input {
  display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
  background: ${T.surface}; border: 0.5px solid ${T.borderGlow}; border-radius: 10px;
  padding: 8px 12px; min-height: 52px; cursor: text; transition: border-color 0.2s, box-shadow 0.2s;
  overflow: hidden;
}
.tags-input:focus-within {
  border-color: ${T.accent}; box-shadow: 0 0 0 3px rgba(58,143,255,0.08);
}
.tag {
  display: flex; align-items: center; gap: 4px; padding: 3px 10px;
  background: rgba(58,143,255,0.1); border: 0.5px solid rgba(58,143,255,0.25);
  border-radius: 100px; font-family: 'Space Mono', monospace; font-size: 11px; color: ${T.accent2};
}
.tag button { background: none; border: none; color: ${T.accent2}; cursor: pointer; font-size: 14px; padding: 0; line-height: 1; opacity: 0.7; }
.tag button:hover { opacity: 1; }
.tags-input input {
  border: none; background: transparent; outline: none; flex: 1; min-width: 120px;
  font-family: 'DM Sans', sans-serif; font-size: 15px; color: #e8f4ff; padding: 4px 4px;
}
.tags-input input::placeholder { color: ${T.textDim}; }
.input-hint { font-size: 11px; color: ${T.textDim}; margin-top: 8px; font-family: 'Space Mono', monospace; text-align: center; }

/* Hint chips */
.examples { margin-top: 14px; display: flex; flex-wrap: wrap; gap: 7px; justify-content: center; }
.chip {
  font-family: 'Space Mono', monospace; font-size: 11px; padding: 4px 13px;
  border: 0.5px solid ${T.border}; border-radius: 100px;
  color: ${T.textMuted}; cursor: pointer; transition: all 0.15s; background: transparent;
}
.chip:hover { border-color: ${T.accent}; color: ${T.accent2}; background: rgba(58,143,255,0.08); }

/* Buttons */
.btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 12px 22px; border-radius: 8px; border: none;
  font-family: 'DM Sans', sans-serif; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: all 0.15s; white-space: nowrap; letter-spacing: 0.02em;
}
.btn-primary { background: ${T.accent}; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #5aa8ff; transform: translateY(-1px); }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }
.btn-ghost { background: transparent; border: 0.5px solid ${T.borderGlow}; color: ${T.textMuted}; }
.btn-ghost:hover { border-color: ${T.accent}; color: ${T.accent2}; }
.btn-danger { background: transparent; border: 0.5px solid rgba(248,113,113,0.3); color: ${T.error}; }
.btn-danger:hover { background: rgba(248,113,113,0.08); }

/* Stats bar */
.stats-bar {
  display: flex; margin: 28px 0 20px;
  background: ${T.surface}; border: 0.5px solid ${T.border};
  border-radius: 10px; overflow: hidden;
}
.stat { flex: 1; padding: 16px 20px; border-right: 0.5px solid ${T.border}; text-align: center; }
.stat:last-child { border-right: none; }
.stat-num { font-family: 'Space Mono', monospace; font-size: 22px; font-weight: 700; color: ${T.accent2}; display: block; }
.stat-num.green { color: ${T.success}; }
.stat-num.warn  { color: ${T.warn}; }
.stat-num.muted { color: ${T.textMuted}; }
.stat-label { font-size: 10px; color: ${T.textDim}; text-transform: uppercase; letter-spacing: 0.1em; margin-top: 3px; display: block; font-family: 'Space Mono', monospace; }

/* Progress */
.progress-wrap { margin: 16px 0 8px; }
.progress-bar-bg { height: 2px; background: ${T.border}; border-radius: 2px; overflow: hidden; }
.progress-bar-fill {
  height: 100%; background: linear-gradient(90deg, ${T.accent}, ${T.accent2});
  border-radius: 2px; transition: width 0.4s ease;
}
.progress-stats {
  display: flex; justify-content: space-between; margin-top: 8px;
  font-family: 'Space Mono', monospace; font-size: 10px; color: ${T.textDim};
}

/* Log */
.status-log {
  margin-top: 10px; padding: 10px 14px;
  background: ${T.bg}; border: 0.5px solid ${T.border}; border-radius: 6px;
  font-family: 'Space Mono', monospace; font-size: 11px; color: ${T.textMuted};
  max-height: 72px; overflow-y: auto;
}
.status-log p { padding: 1px 0; }
.log-scanning { color: ${T.accent2}; }
.log-found    { color: ${T.success}; }
.log-skip     { color: ${T.textDim}; }
.log-error    { color: ${T.error}; }

/* Results toolbar */
.toolbar {
  display: flex; align-items: center; gap: 6px; margin-bottom: 16px; flex-wrap: wrap;
}
.filter-btn {
  font-family: 'Space Mono', monospace; font-size: 11px; padding: 4px 12px;
  border-radius: 100px; border: 0.5px solid ${T.border}; background: transparent;
  color: ${T.textMuted}; cursor: pointer; transition: all 0.15s;
}
.filter-btn.active { border-color: ${T.accent}; color: ${T.accent2}; background: rgba(58,143,255,0.08); }
.filter-btn:hover:not(.active) { border-color: ${T.borderGlow}; color: ${T.text}; }
.result-count-badge {
  margin-left: auto; font-family: 'Space Mono', monospace; font-size: 11px;
  padding: 3px 12px; border-radius: 100px;
  background: rgba(58,143,255,0.08); border: 0.5px solid ${T.borderGlow}; color: ${T.accent2};
}

/* Strain card */
.strain-card {
  border: 0.5px solid ${T.border}; border-radius: 8px;
  margin-bottom: 6px; overflow: hidden; animation: fadeUp 0.25s ease both;
  transition: border-color 0.15s; background: ${T.surface};
}
.strain-card:hover { border-color: ${T.borderGlow}; }
.strain-card.found { border-color: rgba(46,204,140,0.25); }
.strain-card.skip  { opacity: 0.5; }
.strain-header {
  padding: 13px 18px; display: flex; align-items: center; gap: 12px;
  cursor: pointer; transition: background 0.15s;
}
.strain-header:hover { background: rgba(58,143,255,0.03); }
.strain-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.dot-found     { background: ${T.success}; box-shadow: 0 0 6px rgba(46,204,140,0.5); }
.dot-not_found { background: ${T.textDim}; }
.dot-skip      { background: ${T.warn}; }
.dot-scanning  { background: ${T.accent}; animation: pulse 1s infinite; }
.strain-name {
  flex: 1; font-family: 'DM Sans', sans-serif; font-size: 14px; color: ${T.text}; font-style: italic;
}
.strain-acc { font-family: 'Space Mono', monospace; font-size: 11px; color: ${T.textDim}; }
.strain-match-badge {
  font-family: 'Space Mono', monospace; font-size: 11px; padding: 3px 10px;
  background: rgba(46,204,140,0.1); border: 0.5px solid rgba(46,204,140,0.3);
  border-radius: 100px; color: ${T.success};
}
.strain-body { padding: 0 18px 16px; border-top: 0.5px solid ${T.border}; background: ${T.bg}; }

/* Gene table */
.table-wrap { overflow-x: auto; margin-top: 10px; }
table { width: 100%; border-collapse: collapse; }
thead tr { border-bottom: 0.5px solid ${T.border}; }
th {
  font-family: 'Space Mono', monospace; font-size: 9px; letter-spacing: 1.5px;
  color: ${T.textDim}; font-weight: 400; text-transform: uppercase;
  padding: 7px 10px; text-align: left; white-space: nowrap;
}
td {
  font-family: 'Space Mono', monospace; font-size: 11px; padding: 8px 10px;
  color: ${T.textMuted}; border-bottom: 0.5px solid ${T.border};
}
tr:last-child td { border-bottom: none; }
tr:hover td { background: rgba(58,143,255,0.03); }
td.locus  { color: ${T.accent}; }
td.product-cell { color: ${T.text}; max-width: 240px; white-space: normal; word-break: break-word; }
td.product-cell mark { background: rgba(58,143,255,0.18); color: ${T.accent2}; border-radius: 3px; padding: 0 2px; }
td.strand { color: ${T.textMuted}; font-size: 12px; }

.copy-btn {
  background: none; border: none; cursor: pointer; font-size: 11px;
  color: ${T.textDim}; padding: 2px 4px; transition: color 0.2s;
}
.copy-btn:hover { color: ${T.accent}; }

/* Modal */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(4,13,26,0.88);
  backdrop-filter: blur(6px); z-index: 100;
  display: flex; align-items: center; justify-content: center; padding: 24px;
  animation: fadeUp 0.2s ease;
}
.modal {
  background: ${T.surface}; border: 0.5px solid ${T.borderGlow};
  border-radius: 12px; padding: 24px; max-width: 700px; width: 100%;
  max-height: 80vh; overflow-y: auto;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;
}
.fasta-box {
  font-family: 'Space Mono', monospace; font-size: 11px; color: ${T.success};
  background: ${T.bg}; border: 0.5px solid ${T.border}; border-radius: 6px;
  padding: 14px; white-space: pre-wrap; word-break: break-all;
  max-height: 300px; overflow-y: auto; margin-top: 12px;
  line-height: 1.6;
}

/* Summary banner */
.summary-banner {
  display: flex; gap: 0; margin: 20px 0 16px;
  background: ${T.surface}; border: 0.5px solid ${T.border}; border-radius: 10px;
  overflow: hidden; flex-wrap: wrap;
}
.summary-stat { flex: 1; min-width: 100px; text-align: center; padding: 16px 20px; border-right: 0.5px solid ${T.border}; }
.summary-stat:last-child { border-right: none; }
.summary-num { font-family: 'Space Mono', monospace; font-size: 22px; font-weight: 700; color: ${T.accent2}; }
.summary-num.green { color: ${T.success}; }
.summary-num.warn  { color: ${T.warn}; }
.summary-label { font-size: 10px; color: ${T.textDim}; margin-top: 3px; font-family: 'Space Mono', monospace; text-transform: uppercase; letter-spacing: 0.08em; }

/* Loading dots */
.dots span {
  display: inline-block; width: 4px; height: 4px; border-radius: 50%;
  background: ${T.accent}; margin: 0 2px; animation: pulse 1.4s ease infinite;
}
.dots span:nth-child(2) { animation-delay: 0.2s; }
.dots span:nth-child(3) { animation-delay: 0.4s; }

/* NCBI link */
a.ncbi-link {
  color: ${T.accent}; text-decoration: none; font-family: 'Space Mono', monospace; font-size: 11px;
}
a.ncbi-link:hover { text-decoration: underline; }

/* Export btn row */
.export-row { display:flex; gap:8px; margin-top:0; flex-wrap:wrap; align-items:center; }

/* Results card */
.results-card {
  background: ${T.surface}; border: 0.5px solid ${T.border};
  border-radius: 10px; padding: 20px 20px 12px; margin-bottom: 12px;
}

/* Scan action row */
.action-row { display: flex; gap: 8px; margin-top: 20px; flex-wrap: wrap; }
`;

// ─── HELPERS ─────────────────────────────────────────────────────────────────

function highlightProduct(text, queries) {
  let result = text;
  for (const q of queries) {
    const re = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
    result = result.replace(re, "<mark>$1</mark>");
  }
  return result;
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).catch(() => {});
}

function exportCSV(results) {
  const rows = [["Accession", "Strain", "Locus Tag", "Gene", "Product", "Contig", "Start", "Stop", "Strand", "Protein ID"]];
  for (const r of results) {
    if (r.status !== "found") continue;
    for (const m of r.results) {
      rows.push([r.accession, r.strain, m.locus_tag, m.gene, m.product, m.contig, m.start, m.stop, m.strand, m.protein_id]);
    }
  }
  const csv = rows.map(r => r.map(c => `"${(c||"").replace(/"/g,'""')}"`).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a"); a.href = url; a.download = "halomonas_scout_results.csv"; a.click();
  URL.revokeObjectURL(url);
}

function exportJSON(results) {
  const found = results.filter(r => r.status === "found");
  const blob  = new Blob([JSON.stringify(found, null, 2)], { type: "application/json" });
  const url   = URL.createObjectURL(blob);
  const a     = document.createElement("a"); a.href = url; a.download = "halomonas_scout_results.json"; a.click();
  URL.revokeObjectURL(url);
}

// ─── PROTEIN MODAL ────────────────────────────────────────────────────────────
function ProteinModal({ proteinId, onClose }) {
  const [seq, setSeq]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied]  = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/protein-sequence`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ protein_id: proteinId }),
    })
      .then(r => r.json())
      .then(d => { setSeq(d.found ? d.sequence : null); setLoading(false); })
      .catch(() => setLoading(false));
  }, [proteinId]);

  const handleCopy = () => {
    if (seq) { copyToClipboard(seq); setCopied(true); setTimeout(() => setCopied(false), 1500); }
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <div>
            <div style={{fontFamily:"'Space Mono',monospace",fontSize:10,letterSpacing:"0.12em",textTransform:"uppercase",color:T.accent2,marginBottom:6}}>Protein Sekansı</div>
            <div style={{ fontFamily: "'Space Mono',monospace", fontSize: 13, color: T.accent }}>{proteinId}</div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {seq && <button className="btn btn-ghost" onClick={handleCopy}>{copied ? "✓ Kopyalandı" : "Kopyala"}</button>}
            <button className="btn btn-ghost" onClick={onClose}>✕ Kapat</button>
          </div>
        </div>
        {loading && <div style={{ padding: 20, textAlign: "center", color: T.textMuted }}>
          <div className="dots"><span/><span/><span/></div>
        </div>}
        {!loading && seq && <div className="fasta-box">{seq}</div>}
        {!loading && !seq && <div style={{ color: T.error, fontFamily: "'Space Mono',monospace", fontSize: 12 }}>Sekans bulunamadı.</div>}
      </div>
    </div>
  );
}

// ─── STRAIN CARD ─────────────────────────────────────────────────────────────
function StrainCard({ item, productQueries, onProteinClick }) {
  const [open, setOpen] = useState(false);
  const isFound    = item.status === "found";
  const isScanning = item.status === "scanning";

  return (
    <div className={`strain-card ${item.status}`}>
      <div className="strain-header" onClick={() => isFound && setOpen(o => !o)}>
        <div className={`strain-dot dot-${item.status}`} />
        <div className="strain-name">{item.strain || "Halomonas sp."}</div>
        <div className="strain-acc">{item.accession}</div>
        {isFound && <div className="strain-match-badge">+{item.match_count} gen</div>}
        {isScanning && <div className="dots"><span/><span/><span/></div>}
        {isFound && <span style={{ color: T.textMuted, fontSize: 14 }}>{open ? "▲" : "▼"}</span>}
      </div>

      {isFound && open && (
        <div className="strain-body">
          <div style={{ display: "flex", gap: 14, marginBottom: 10, flexWrap: "wrap", paddingTop: 14 }}>
            {item.ncbi_url && (
              <a className="ncbi-link" href={item.ncbi_url} target="_blank" rel="noreferrer">
                ↗ NCBI Assembly
              </a>
            )}
            {item.biosample && (
              <a className="ncbi-link" href={`https://www.ncbi.nlm.nih.gov/biosample/${item.biosample}`} target="_blank" rel="noreferrer">
                ↗ BioSample
              </a>
            )}
            <span style={{ fontFamily: "'Space Mono',monospace", fontSize: 10, color: T.textDim }}>
              Kaynak: {item.source}
            </span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Locus Tag</th>
                  <th>Gen</th>
                  <th>Ürün</th>
                  <th>Contig</th>
                  <th>Konum</th>
                  <th>IP</th>
                  <th>Sekans</th>
                </tr>
              </thead>
              <tbody>
                {item.results.map((r, i) => (
                  <tr key={i}>
                    <td className="locus">
                      {r.locus_tag}
                      {r.locus_tag && <button className="copy-btn" title="Kopyala" onClick={() => copyToClipboard(r.locus_tag)}>⎘</button>}
                    </td>
                    <td>{r.gene || "—"}</td>
                    <td className="product-cell"
                      dangerouslySetInnerHTML={{ __html: highlightProduct(r.product, productQueries) }} />
                    <td style={{ maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.contig}
                    </td>
                    <td className="strand">
                      {r.start}–{r.stop}
                      <span style={{ marginLeft: 4 }}>{r.strand === "+" ? "→" : "←"}</span>
                    </td>
                    <td>
                      {r.protein_id ? (
                        <span style={{ color: T.accent, cursor: "pointer", fontFamily: "'Space Mono',monospace", fontSize: 11 }}
                          onClick={() => onProteinClick(r.protein_id)}>
                          {r.protein_id}
                        </span>
                      ) : "—"}
                    </td>
                    <td>
                      {r.protein_id ? (
                        <button className="btn btn-ghost" style={{ padding: "2px 8px", fontSize: 10 }}
                          onClick={() => onProteinClick(r.protein_id)}>
                          FASTA
                        </button>
                      ) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── MAIN APP ─────────────────────────────────────────────────────────────────
export default function App() {
  // Input state
  const [productTags, setProductTags] = useState([]);
  const [tagInput, setTagInput]       = useState("");

  // Scan state
  const [scanning, setScanning]       = useState(false);
  const [results, setResults]         = useState([]);  // {accession, strain, status, ...}
  const [logs, setLogs]               = useState([]);
  const [progress, setProgress]       = useState({ current: 0, total: 0 });
  const [summary, setSummary]         = useState(null);
  const [ncbiCount, setNcbiCount]     = useState(null);

  // Filter
  const [filter, setFilter]           = useState("all"); // all | found | not_found | skip

  // Protein modal
  const [proteinModal, setProteinModal] = useState(null);

  const evtRef   = useRef(null);
  const logBoxRef = useRef(null);

  // NCBI count
  useEffect(() => {
    fetch(`${API_BASE}/count`)
      .then(r => r.json())
      .then(d => setNcbiCount(d.count))
      .catch(() => {});
  }, []);

  const addLog = useCallback((cls, msg) => {
    setLogs(l => [...l.slice(-40), { cls, msg, id: Date.now() + Math.random() }]);
    setTimeout(() => {
      if (logBoxRef.current) logBoxRef.current.scrollTop = logBoxRef.current.scrollHeight;
    }, 50);
  }, []);

  const addTag = (val) => {
    const v = val.trim().toLowerCase();
    if (v && !productTags.includes(v)) setProductTags(t => [...t, v]);
    setTagInput("");
  };

  const startScan = () => {
    if (!productTags.length || scanning) return;
    setScanning(true);
    setResults([]);
    setLogs([]);
    setSummary(null);
    setProgress({ current: 0, total: 0 });

    const params = new URLSearchParams({
      product: productTags.join(","),
    });

    const url = `${API_BASE}/scan?${params}`;
    if (evtRef.current) evtRef.current.close();
    const evt = new EventSource(url);
    evtRef.current = evt;

    evt.onmessage = (e) => {
      const data = JSON.parse(e.data.trim());
      const { type } = data;

      if (type === "status") {
        addLog("log-scanning", `⟳ ${data.message}`);
      } else if (type === "assembly_list") {
        addLog("log-scanning", `◈ NCBI: ${data.total_in_ncbi} kayıt, ${data.to_scan} taranacak`);
        setProgress(p => ({ ...p, total: data.to_scan }));
      } else if (type === "scanning") {
        setProgress(p => ({ current: data.progress, total: data.total }));
        addLog("log-scanning", `→ [${data.progress}/${data.total}] ${data.accession}`);
        // Scanning placeholder
        setResults(prev => {
          if (prev.find(r => r.accession === data.accession)) return prev;
          return [...prev, {
            accession: data.accession,
            strain:    data.strain,
            status:    "scanning",
            assembly:  data.assembly,
          }];
        });
      } else if (type === "found") {
        setResults(prev => prev.map(r => r.accession === data.accession ? { ...data, status: "found" } : r));
        addLog("log-found", `✓ ${data.accession}: ${data.match_count} eşleşme`);
      } else if (type === "not_found") {
        setResults(prev => prev.map(r => r.accession === data.accession ? { ...data, status: "not_found" } : r));
      } else if (type === "skip") {
        setResults(prev => prev.map(r => r.accession === data.accession
          ? { ...data, status: "skip" }
          : prev.find(p => p.accession === data.accession) ? r
          : r
        ));
        // If not already in list, add
        setResults(prev => {
          if (prev.find(r => r.accession === data.accession)) return prev;
          return [...prev, { ...data, status: "skip" }];
        });
        addLog("log-skip", `⊘ ${data.accession}: ${data.reason}`);
      } else if (type === "error") {
        addLog("log-error", `✕ ${data.message}`);
      } else if (type === "done") {
        setSummary(data);
        setScanning(false);
        addLog("log-found", `■ Bitti — ${data.found_count} pozitif / ${data.total_scanned} tarandı`);
        evt.close();
      }
    };

    evt.onerror = () => {
      addLog("log-error", "✕ Bağlantı hatası.");
      setScanning(false);
      evt.close();
    };
  };

  const stopScan = () => {
    if (evtRef.current) evtRef.current.close();
    setScanning(false);
    addLog("log-error", "■ Kullanıcı tarafından durduruldu.");
  };

  // Filtered results
  const filteredResults = results.filter(r => {
    if (filter === "all")       return r.status !== "scanning";
    if (filter === "found")     return r.status === "found";
    if (filter === "not_found") return r.status === "not_found";
    if (filter === "skip")      return r.status === "skip";
    return true;
  });
  const foundCount    = results.filter(r => r.status === "found").length;
  const notFoundCount = results.filter(r => r.status === "not_found").length;
  const skipCount     = results.filter(r => r.status === "skip").length;
  const pct = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0;

  return (
    <>
      <style>{CSS}</style>
      <div className="salt-bg" />
      <div className="salt-crystals" />
      <div className="scan-line" />

      <div className="app">
        {/* Header bar */}
        <div className="header-bar" style={{width:"100%",maxWidth:"100%",boxSizing:"border-box"}}>
          <div className="logo-wrap">
            <span className="logo-text">HalomonasScout</span>
            <span className="logo-sub">NCBI Gene Explorer</span>
          </div>
          <div style={{display:"flex",alignItems:"center",gap:16}}>
            <span className="header-pill">
              <span className="header-pill-dot"/>
              {ncbiCount !== null ? ncbiCount : 466} assembly
            </span>
            <span style={{fontFamily:"'Space Mono',monospace",fontSize:11,color:T.textDim}}>v1.0.0</span>
          </div>
        </div>

        <div className="container">
          {/* Hero */}
          <div className="hero">
            <p className="hero-eyebrow">Halomonas sp. · Uncharacterized isolates · NCBI</p>
            <h1 className="hero-title">Gen tara,<br/><span>hızla bul.</span></h1>
            <p className="hero-desc">466 tanımlanmamış Halomonas sp. izolatının tüm genomlarında gen ve enzim taraması. NCBI GBFF tabanlı, GO annotation dahil.</p>

            {/* Search */}
            <div className="search-outer">
              <div className="tags-input" onClick={() => document.getElementById("tag-input").focus()}>
              {productTags.map(t => (
                <span key={t} className="tag">
                  {t}
                  <button onClick={() => setProductTags(p => p.filter(x => x !== t))}>×</button>
                </span>
              ))}
              <input
                id="tag-input"
                value={tagInput}
                onChange={e => setTagInput(e.target.value)}
                onKeyDown={e => {
                  if ((e.key === "Enter" || e.key === ",") && tagInput) { e.preventDefault(); addTag(tagInput); }
                  if (e.key === "Backspace" && !tagInput && productTags.length) setProductTags(p => p.slice(0,-1));
                }}
                placeholder={productTags.length === 0 ? "gen/ürün yaz, Enter ile ekle…" : ""}
                disabled={scanning}
              />
            </div>
              <div className="input-hint">Enter veya virgül ile ekle (örn: ectoine, betaine)</div>
              <div className="examples">
                {GENE_EXAMPLES.map(ex => (
                  <button key={ex} className="chip" onClick={() => !productTags.includes(ex) && setProductTags(p => [...p, ex])}>
                    {ex}
                  </button>
                ))}
              </div>

              {/* Buttons */}
              <div className="action-row" style={{justifyContent:"center",marginTop:20}}>
                <button className="btn btn-primary" onClick={startScan}
                  disabled={!productTags.length || scanning}>
                  {scanning ? <><span className="dots"><span/><span/><span/></span> Taranıyor…</> : "Tara →"}
                </button>
                {scanning && (
                  <button className="btn btn-danger" onClick={stopScan}>■ Durdur</button>
                )}
                {results.length > 0 && !scanning && (
                  <button className="btn btn-ghost" onClick={() => { setResults([]); setSummary(null); setLogs([]); }}>
                    Temizle
                  </button>
                )}
              </div>
            </div>{/* /search-outer */}
          </div>{/* /hero */}

          {/* Stats bar */}
          {(scanning || results.length > 0) && (
            <div className="stats-bar">
              <div className="stat">
                <span className="stat-num">{progress.total || 466}</span>
                <span className="stat-label">Assembly</span>
              </div>
              <div className="stat">
                <span className="stat-num green">{foundCount}</span>
                <span className="stat-label">Pozitif</span>
              </div>
              <div className="stat">
                <span className="stat-num muted">{notFoundCount}</span>
                <span className="stat-label">Bulunamadı</span>
              </div>
              <div className="stat">
                <span className="stat-num warn">{progress.total > 0 ? progress.total - progress.current : 0}</span>
                <span className="stat-label">Bekliyor</span>
              </div>
            </div>
          )}

          {/* Progress */}
          {(scanning || progress.current > 0) && (
            <div className="progress-wrap">
              <div className="progress-bar-bg">
                <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
              </div>
              <div className="progress-stats">
                <span>{progress.current} / {progress.total} tarandı</span>
                <span style={{ color: T.success }}>✓ {foundCount} pozitif</span>
                <span>{pct}%</span>
              </div>
            </div>
          )}

          {/* Log */}
          {logs.length > 0 && (
            <div className="status-log" ref={logBoxRef}>
              {logs.map(l => <p key={l.id} className={l.cls}>{l.msg}</p>)}
              {scanning && <p className="log-scanning">█<span style={{ animation: "blink 1s infinite" }}>_</span></p>}
            </div>
          )}

          {/* Export row when done */}
          {summary && (
            <div style={{display:"flex",justifyContent:"flex-end",marginBottom:12}}>
              <div className="export-row">
                <button className="btn btn-ghost" onClick={() => exportCSV(results)}>↓ CSV</button>
                <button className="btn btn-ghost" onClick={() => exportJSON(results)}>↓ JSON</button>
              </div>
            </div>
          )}

          {/* Results */}
          {results.filter(r => r.status !== "scanning").length > 0 && (
            <div className="results-card">
              <div className="toolbar">
                {[
                  { key: "all",       label: "Tümü",        count: results.filter(r=>r.status!=="scanning").length },
                  { key: "found",     label: "Pozitif",      count: foundCount },
                  { key: "not_found", label: "Bulunamadı",   count: notFoundCount },
                  { key: "skip",      label: "Atlandı",      count: skipCount },
                ].map(f => (
                  <button key={f.key} className={`filter-btn ${filter===f.key?"active":""}`}
                    onClick={() => setFilter(f.key)}>
                    {f.label} ({f.count})
                  </button>
                ))}
                {filter === "found" && productTags.length > 0 && (
                  <span style={{ fontFamily: "'Space Mono',monospace", fontSize: 10, color: T.textDim, marginLeft: 4 }}>
                    arama: {productTags.join(", ")}
                  </span>
                )}
              </div>

              {filteredResults.map(item => (
                <StrainCard
                  key={item.accession}
                  item={item}
                  productQueries={productTags}
                  onProteinClick={id => setProteinModal(id)}
                />
              ))}

              {filteredResults.length === 0 && (
                <div style={{ textAlign: "center", padding: 32, color: T.textDim, fontFamily: "'Space Mono',monospace", fontSize: 12 }}>
                  Bu kategoride sonuç yok.
                </div>
              )}
            </div>
          )}

          {/* Scanning live items */}
          {scanning && results.filter(r => r.status === "scanning").map(item => (
            <StrainCard key={item.accession} item={item} productQueries={productTags} onProteinClick={() => {}} />
          ))}
        </div>{/* /container */}
      </div>{/* /app */}

      {/* Protein Modal */}
      {proteinModal && (
        <ProteinModal proteinId={proteinModal} onClose={() => setProteinModal(null)} />
      )}
    </>
  );
}
