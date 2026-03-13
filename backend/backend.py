"""
HalomonasScout — Backend
Halomonas sp. (tanımlanmamış) izolatları için NCBI-tabanlı gen tarayıcı.
Mevcut DeepDive uygulamasından BAĞIMSIZ çalışır.
"""

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import re, json, gzip, requests, urllib.parse, time, os, hashlib, pickle, threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

app = Flask(__name__)
CORS(app)

# ─── GENES DATABASE ───────────────────────────────────────────────────────────
_GENES_DB = None

def load_genes_db() -> dict | None:
    """halomonas_genes.json.gz dosyasını yükle (lazy, bir kere)."""
    global _GENES_DB
    if _GENES_DB is not None:
        return _GENES_DB
    script_dir = os.path.dirname(os.path.abspath(__file__))
    gz_path  = os.path.join(script_dir, "halomonas_genes.json.gz")
    json_path = os.path.join(script_dir, "halomonas_genes.json")
    try:
        if os.path.exists(gz_path):
            print(f"[GENES_DB] {gz_path} yükleniyor...")
            with gzip.open(gz_path, "rt", encoding="utf-8") as f:
                _GENES_DB = json.load(f)
            print(f"[GENES_DB] {len(_GENES_DB.get('assemblies', {}))} assembly yüklendi")
            return _GENES_DB
        elif os.path.exists(json_path):
            print(f"[GENES_DB] {json_path} yükleniyor...")
            with open(json_path, "r", encoding="utf-8") as f:
                _GENES_DB = json.load(f)
            print(f"[GENES_DB] {len(_GENES_DB.get('assemblies', {}))} assembly yüklendi")
            return _GENES_DB
    except Exception as e:
        print(f"[GENES_DB] Yükleme hatası: {e}")
    return None

# ─── CACHE ────────────────────────────────────────────────────────────────────
CACHE_DIR = os.environ.get("CACHE_DIR", "/tmp/haloscout_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL = 60 * 60 * 24 * 30  # 30 gün

def _cache_path(key: str) -> str:
    return os.path.join(CACHE_DIR, hashlib.md5(key.encode()).hexdigest() + ".pkl")

def cache_get(key: str):
    path = _cache_path(key)
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                entry = pickle.load(f)
            if (time.time() - entry["ts"]) < CACHE_TTL:
                return entry["data"]
        except Exception:
            pass
    return None

def cache_set(key: str, data):
    try:
        with open(_cache_path(key), "wb") as f:
            pickle.dump({"data": data, "ts": time.time()}, f)
    except Exception:
        pass

HEADERS = {
    "User-Agent": "HalomonasScout/1.0 (research tool; contact: researcher@example.com)",
}

NCBI_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# ─── NCBI ASSEMBLY ARAMA ─────────────────────────────────────────────────────

TSV_PATH = os.path.join(os.path.dirname(__file__), "halomonas_sp.tsv")

def load_assemblies_from_tsv() -> list[dict]:
    """
    halomonas_sp.tsv dosyasından assembly listesini yükle.
    NCBI Data Hub'dan indirilen TSV — strain/isolate adları burada kesin olarak var.
    GCF öncelikli (RefSeq), GCF yoksa GCA kullan.
    """
    import csv
    if not os.path.exists(TSV_PATH):
        print(f"[WARN] TSV bulunamadı: {TSV_PATH}")
        return []

    rows = []
    with open(TSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            rows.append(r)

    # Sadece "sp." içeren organizmalar
    rows = [r for r in rows if " sp." in r.get("Organism Name", "")]

    # GCF öncelikli unique assembly'ler
    best = {}
    for r in rows:
        acc  = r.get("Assembly Accession", "").strip()
        name = r.get("Assembly Name", acc)
        if acc.startswith("GCF_"):
            best[name] = r
        elif name not in best:
            best[name] = r

    assemblies = []
    for r in best.values():
        acc     = r.get("Assembly Accession", "").strip()
        strain  = r.get("Organism Infraspecific Names Strain", "").strip()
        isolate = r.get("Organism Infraspecific Names Isolate", "").strip()
        species = r.get("Organism Name", "Halomonas sp.").strip()

        # Display name: Organism Name zaten strain içeriyorsa tekrar ekleme
        # Örn: "Halomonas sp. THAF12" + strain="THAF12" → sadece "Halomonas sp. THAF12"
        tag = strain or isolate
        if tag and tag.lower() not in species.lower():
            display_name = f"{species} {tag}"
        else:
            display_name = species

        # FTP path'i TSV'de yok, boş bırakıyoruz — find_gff_url_by_accession devreye girecek
        assemblies.append({
            "accession":      acc,
            "strain_name":    display_name,
            "strain_tag":     strain or isolate,
            "assembly_name":  r.get("Assembly Name", ""),
            "assembly_status": r.get("Assembly Level", ""),
            "biosample":      r.get("Assembly BioSample Accession", ""),
            "ftp_refseq":     "",
            "ftp_genbank":    "",
            "taxid":          r.get("Organism Taxonomic ID", ""),
            "submissiondate": r.get("Assembly Release Date", ""),
            "total_count":    len(best),
        })

    print(f"[TSV] {len(assemblies)} unique assembly yüklendi")
    return assemblies


def search_halomonas_sp_assemblies(extra_term: str = "", retmax: int = 10000) -> list[dict]:
    """TSV dosyasından yükle, yoksa NCBI API'ye düş."""
    assemblies = load_assemblies_from_tsv()
    if assemblies:
        return assemblies

    # Fallback: NCBI API
    cached = cache_get(f"assembly_list_api")
    if cached:
        return cached
    try:
        es = requests.get(f"{NCBI_EUTILS}/esearch.fcgi", params={
            "db": "assembly", "term": '"Halomonas sp."[Organism]',
            "retmode": "json", "retmax": retmax, "sort": "submissiondate desc",
        }, headers=HEADERS, timeout=(10, 30))
        es.raise_for_status()
        result = es.json().get("esearchresult", {})
        ids = result.get("idlist", [])
        total_count = int(result.get("count", 0))
    except Exception as e:
        print(f"[WARN] NCBI esearch hatası: {e}")
        return []
    if not ids:
        return []
    assemblies = []
    for i in range(0, len(ids), 50):
        batch = ids[i:i+50]
        try:
            es2 = requests.get(f"{NCBI_EUTILS}/esummary.fcgi", params={
                "db": "assembly", "id": ",".join(batch), "retmode": "json",
            }, headers=HEADERS, timeout=(10, 30))
            es2.raise_for_status()
            result2 = es2.json().get("result", {})
            for uid in batch:
                doc = result2.get(uid, {})
                if not doc: continue
                accession = (doc.get("assemblyaccession") or
                             doc.get("synonym", {}).get("refseq") or
                             doc.get("synonym", {}).get("genbank"))
                if not accession: continue
                species = doc.get("speciesname", "Halomonas sp.")
                strain_tag = isolate_tag = ""
                for entry in (doc.get("infraspecific_names") or []):
                    t = entry.get("sub_type","").lower(); v = entry.get("sub_value","").strip()
                    if t == "strain" and v: strain_tag = v
                    elif t == "isolate" and v and not strain_tag: isolate_tag = v
                display_name = (f"{species} {strain_tag}" if strain_tag else
                                f"{species} {isolate_tag}" if isolate_tag else species)
                assemblies.append({"accession": accession, "strain_name": display_name,
                    "strain_tag": strain_tag or isolate_tag, "assembly_name": doc.get("assemblyname",""),
                    "assembly_status": doc.get("assemblystatus",""), "biosample": doc.get("biosample",""),
                    "ftp_refseq": doc.get("ftppath_refseq",""), "ftp_genbank": doc.get("ftppath_genbank",""),
                    "taxid": doc.get("taxid",""), "submissiondate": doc.get("submissiondate",""),
                    "total_count": total_count})
        except Exception as e:
            print(f"[WARN] ESummary hatası: {e}"); continue
        time.sleep(0.15)
    cache_set("assembly_list_api", assemblies)
    return assemblies


def find_gff_url_from_ftp(ftp_path: str) -> str | None:
    """FTP path'inden .gff.gz URL'sini çıkar."""
    if not ftp_path:
        return None
    ftp_url = ftp_path.replace("ftp://", "https://") + "/"
    try:
        r = requests.get(ftp_url, headers=HEADERS, timeout=(8, 15))
        if not r.ok:
            return None
        files = re.findall(r'href="([^"]+_genomic\.gff\.gz)"', r.text)
        if files:
            fname = files[0]
            return fname if fname.startswith("http") else ftp_url + fname
    except Exception:
        pass
    return None


def find_gff_url_by_accession(accession: str) -> str | None:
    """Accession'dan GFF URL'si bul — önce NCBI esearch, sonra FTP dizin tarama."""
    cached = cache_get(f"gff_url_{accession}")
    if cached:
        return cached

    acc_base = accession.split(".")[0]

    # 1. ESummary'den FTP path al
    try:
        es = requests.get(f"{NCBI_EUTILS}/esearch.fcgi", params={
            "db": "assembly", "term": acc_base, "retmode": "json"
        }, headers=HEADERS, timeout=(8, 15))
        ids = es.json().get("esearchresult", {}).get("idlist", [])
        if ids:
            es2 = requests.get(f"{NCBI_EUTILS}/esummary.fcgi", params={
                "db": "assembly", "id": ids[0], "retmode": "json"
            }, headers=HEADERS, timeout=(8, 15))
            doc = es2.json().get("result", {}).get(ids[0], {})
            for ftp_key in ["ftppath_refseq", "ftppath_genbank"]:
                url = find_gff_url_from_ftp(doc.get(ftp_key, ""))
                if url:
                    cache_set(f"gff_url_{accession}", url)
                    return url
    except Exception:
        pass

    # 2. Direkt FTP dizin tarama
    digits = re.sub(r"\D", "", acc_base)
    if len(digits) >= 9:
        d1, d2, d3 = digits[:3], digits[3:6], digits[6:9]
        for prefix in ["GCF", "GCA"]:
            ftp_base = f"https://ftp.ncbi.nlm.nih.gov/genomes/all/{prefix}/{d1}/{d2}/{d3}/"
            try:
                r = requests.get(ftp_base, headers=HEADERS, timeout=(8, 15))
                if not r.ok:
                    continue
                folders = re.findall(r'href="([^"\']+/)"', r.text)
                for folder in folders:
                    folder = folder.strip("/")
                    if acc_base in folder:
                        folder_url = ftp_base + folder + "/"
                        r2 = requests.get(folder_url, headers=HEADERS, timeout=(8, 15))
                        files = re.findall(r'href="([^"\']+_genomic\.gff\.gz)"', r2.text)
                        if files:
                            fname = files[0]
                            url = fname if fname.startswith("http") else folder_url + fname
                            cache_set(f"gff_url_{accession}", url)
                            return url
            except Exception:
                continue
    return None


# ─── ANNOTATION İNDİR ────────────────────────────────────────────────────────

def download_annotation(accession: str, ftp_refseq: str = "", ftp_genbank: str = "") -> tuple[str | None, str]:
    """GFF annotation'ı indir. Returns (content, source_label)."""
    cached = cache_get(f"annotation_{accession}")
    if cached:
        print(f"[CACHE HIT] {accession}")
        return cached, "cache"

    # 1. Önce GBFF dene — GO term isimleri yazıyla geliyor (levansucrase activity gibi)
    gbff_url = find_gbff_url_by_accession(accession)
    if gbff_url:
        try:
            content = _download_gff(gbff_url)
            if content:
                cache_set(f"annotation_{accession}", content)
                print(f"[GBFF] {accession} indirildi")
                return content, "NCBI GBFF"
        except Exception as e:
            print(f"[WARN] GBFF download hata ({accession}): {e}")

    # 2. GBFF yoksa GFF dene
    for ftp in [ftp_refseq, ftp_genbank]:
        url = find_gff_url_from_ftp(ftp)
        if url:
            try:
                content = _download_gff(url)
                if content:
                    cache_set(f"annotation_{accession}", content)
                    return content, "NCBI GFF (FTP)"
            except Exception as e:
                print(f"[WARN] FTP download hata: {e}")

    gff_url = find_gff_url_by_accession(accession)
    if gff_url:
        try:
            content = _download_gff(gff_url)
            if content:
                cache_set(f"annotation_{accession}", content)
                return content, "NCBI GFF"
        except Exception as e:
            print(f"[WARN] GFF download hata ({accession}): {e}")

    return None, "indirilemedi"


def find_gbff_url_by_accession(accession: str) -> str | None:
    """GFF bulunamazsa GBFF URL'si ara."""
    acc_base = accession.split(".")[0]
    digits = re.sub(r"\D", "", acc_base)
    if len(digits) >= 9:
        d1, d2, d3 = digits[:3], digits[3:6], digits[6:9]
        for prefix in ["GCF", "GCA"]:
            ftp_base = f"https://ftp.ncbi.nlm.nih.gov/genomes/all/{prefix}/{d1}/{d2}/{d3}/"
            try:
                r = requests.get(ftp_base, headers=HEADERS, timeout=(8, 15))
                if not r.ok:
                    continue
                folders = re.findall(r'href="([^"\']+/)"', r.text)
                for folder in folders:
                    folder = folder.strip("/")
                    if acc_base in folder:
                        folder_url = ftp_base + folder + "/"
                        r2 = requests.get(folder_url, headers=HEADERS, timeout=(8, 15))
                        files = re.findall(r'href="([^"\']+_genomic\.gbff\.gz)"', r2.text)
                        if files:
                            fname = files[0]
                            return fname if fname.startswith("http") else folder_url + fname
            except Exception:
                continue
    return None


def _download_gff(url: str, max_mb: int = 80) -> str | None:
    """GFF dosyasını indir, decompress et."""
    def _fetch():
        chunks = []
        with requests.get(url, headers=HEADERS, timeout=(10, 90), stream=True) as r:
            r.raise_for_status()
            size = 0
            for chunk in r.iter_content(chunk_size=65536):
                chunks.append(chunk)
                size += len(chunk)
                if size > max_mb * 1024 * 1024:
                    raise Exception(f"Dosya çok büyük (>{max_mb}MB)")
        return b"".join(chunks)

    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(_fetch)
        try:
            raw = future.result(timeout=30)
        except FuturesTimeout:
            future.cancel()
            raise Exception("GFF indirme timeout (30s)")

    if url.endswith(".gz"):
        return gzip.decompress(raw).decode("utf-8", errors="replace")
    return raw.decode("utf-8", errors="replace")


# ─── PARSE GFF ────────────────────────────────────────────────────────────────

# ─── GO TERM EŞLEŞTİRME ─────────────────────────────────────────────────────
# Kullanıcı keyword → ilgili GO ID'leri
GO_TERM_MAP = {
    "levan":           ["GO:0050053", "GO:0000016", "GO:0009011"],
    "levansucrase":    ["GO:0050053"],
    "ectoine":         ["GO:0019491", "GO:0009400"],
    "betaine":         ["GO:0019285", "GO:0031427"],
    "cellulose":       ["GO:0030244", "GO:0008703"],
    "alginate":        ["GO:0042121", "GO:0016762"],
    "exopolysaccharide":["GO:0045259", "GO:0033692"],
    "catalase":        ["GO:0004096"],
    "superoxide":      ["GO:0004784"],
    "lipase":          ["GO:0016298", "GO:0004620"],
    "protease":        ["GO:0008233", "GO:0004175"],
    "amylase":         ["GO:0004556", "GO:0004553"],
    "osmoprotectant":  ["GO:0009415", "GO:0006970"],
    "compatible solute":["GO:0006970"],
    "fructan":         ["GO:0050053", "GO:0009011"],
    "sucrase":         ["GO:0050053", "GO:0004575"],
}

def get_go_ids_for_query(query: str) -> list[str]:
    """Keyword için ilgili GO ID'lerini döndür."""
    q = query.lower().strip()
    ids = []
    for key, go_list in GO_TERM_MAP.items():
        if q in key or key in q:
            ids.extend(go_list)
    return list(set(ids))


def parse_gff(content: str, product_queries: list[str]) -> list[dict]:
    """GFF dosyasından eşleşen ürünleri bul. product + GO ID + note alanlarına bakar."""
    queries_lc = [q.lower().strip() for q in product_queries]
    # Her query için GO ID'leri hazırla
    query_go_ids = {q: get_go_ids_for_query(q) for q in queries_lc}
    matches = []
    for line in content.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 9:
            continue
        contig, source, feat_type, start, stop, score, strand, phase, attrs = parts[:9]
        attr_dict = {}
        for attr in attrs.split(";"):
            if "=" in attr:
                k, v = attr.split("=", 1)
                attr_dict[k.strip()] = urllib.parse.unquote(v.strip())

        product  = attr_dict.get("product", "")
        dbxref   = attr_dict.get("Dbxref", "")  # GO:0050053 gibi ID'ler burada
        note     = attr_dict.get("Note", attr_dict.get("note", ""))
        combined = f"{product} {dbxref} {note}".lower()

        if not combined.strip():
            continue

        matched = []
        match_field = "product"
        for q in queries_lc:
            # 1. Direkt kelime eşleşmesi
            if q in combined:
                matched.append(q)
            # 2. GO ID eşleşmesi
            elif any(go_id.lower() in dbxref.lower() for go_id in query_go_ids.get(q, [])):
                matched.append(q)
                match_field = "GO ID"

        if not matched:
            continue

        if match_field != "GO ID":
            match_field = "product" if any(q in product.lower() for q in queries_lc) else "note"

        matches.append({
            "locus_tag":    attr_dict.get("locus_tag", ""),
            "gene":         attr_dict.get("gene", ""),
            "product":      product,
            "protein_id":   attr_dict.get("protein_id", ""),
            "contig":       contig,
            "start":        start,
            "stop":         stop,
            "strand":       strand,
            "type":         feat_type,
            "matched_query": matched[0],
            "match_field":  match_field,
            "note":         attr_dict.get("Note", attr_dict.get("note", "")),
        })
    return matches


# ─── GBFF PARSER ─────────────────────────────────────────────────────────────

def parse_gbff(content: str, product_queries: list[str]) -> list[dict]:
    """GBFF dosyasından eşleşen ürünleri bul. product + GO_function + note alanlarına bakar."""
    queries_lc = [q.lower().strip() for q in product_queries]
    matches = []
    current_feature = None
    current_attrs   = {}
    current_location = ""
    current_contig  = ""
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("LOCUS"):
            parts = line.split()
            if len(parts) > 1:
                current_contig = parts[1]
        feat_match = re.match(r'^     (\w+)\s+(.+)$', line)
        if feat_match:
            if current_feature and current_attrs:
                product  = current_attrs.get("product", "")
                go_func  = current_attrs.get("GO_function", "") + " " + current_attrs.get("GO_process", "")
                note     = current_attrs.get("note", "")
                combined = f"{product} {go_func} {note}".lower()
                matched  = [q for q in queries_lc if q in combined]
                if matched:
                    match_field = "product" if any(q in product.lower() for q in queries_lc) else "GO/note"
                    loc = current_location
                    strand = "-" if "complement" in loc else "+"
                    coords = re.findall(r'\d+', loc)
                    matches.append({
                        "locus_tag":    current_attrs.get("locus_tag", ""),
                        "gene":         current_attrs.get("gene", ""),
                        "product":      product,
                        "protein_id":   current_attrs.get("protein_id", ""),
                        "contig":       current_contig,
                        "start":        coords[0] if coords else "",
                        "stop":         coords[-1] if len(coords) > 1 else "",
                        "strand":       strand,
                        "type":         current_feature,
                        "matched_query": matched[0],
                        "match_field":  match_field,
                        "note":         note,
                    })
            current_feature  = feat_match.group(1)
            current_location = feat_match.group(2).strip()
            current_attrs    = {}
        elif line.startswith('                     /'):
            attr_line = line.strip().lstrip('/')
            if '="' in attr_line:
                key, val = attr_line.split('="', 1)
                val = val.rstrip('"')
                while (i + 1 < len(lines)
                       and not lines[i+1].strip().startswith('/')
                       and lines[i+1].startswith('                     ')
                       and not re.match(r'^     \w+\s+', lines[i+1])):
                    i += 1
                    val = val + " " + lines[i].strip().rstrip('"')
                current_attrs[key.strip()] = val.strip()
        i += 1
    return matches


def parse_annotation(content: str, product_queries: list[str]) -> list[dict]:
    """İçeriğin tipine göre doğru parser'ı çağır."""
    if content and "LOCUS" in content[:500] and "FEATURES" in content:
        return parse_gbff(content, product_queries)
    return parse_gff(content, product_queries)


# ─── PROTEIN SEKANS ───────────────────────────────────────────────────────────

def fetch_protein_sequence(protein_id: str) -> str | None:
    if not protein_id:
        return None
    try:
        r = requests.get(f"{NCBI_EUTILS}/efetch.fcgi", params={
            "db": "protein", "id": protein_id,
            "rettype": "fasta", "retmode": "text",
        }, headers=HEADERS, timeout=(8, 15))
        if r.ok and r.text.startswith(">"):
            return r.text.strip()
    except Exception as e:
        print(f"[WARN] Protein sekans hatası: {e}")
    return None


# ─── SSE HELPER ───────────────────────────────────────────────────────────────

def sse(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    padding = " " * max(0, 4096 - len(payload))
    return f"data: {payload}{padding}\n\n"


# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "app": "HalomonasScout"})


@app.route("/count", methods=["GET"])
def count_assemblies():
    """TSV'deki assembly sayısını döndür."""
    assemblies = load_assemblies_from_tsv()
    return jsonify({"count": len(assemblies)})


@app.route("/scan", methods=["GET"])
def scan():
    """
    SSE endpoint: Halomonas sp. assembly'lerini tara, belirtilen gen/ürünleri ara.
    
    Query params:
        product  : str  — virgülle ayrılmış gen/ürün adları (örn: "ectoine,betaine")
        retmax   : int  — kaç assembly taransın (default: 100, max: 500)
        filter   : str  — isteğe bağlı NCBI filtre terimi
    """
    product_raw = request.args.get("product", "").strip()
    # retmax=0 veya verilmezse → tüm kayıtlar (NCBI'da ne kadar varsa)
    retmax_raw = request.args.get("retmax", "0").strip()
    retmax = int(retmax_raw) if retmax_raw.isdigit() and int(retmax_raw) > 0 else 10000
    extra_filter = request.args.get("filter", "").strip()

    if not product_raw:
        return jsonify({"error": "product parametresi gerekli"}), 400

    product_queries = [p.strip() for p in product_raw.split(",") if p.strip()]

    def generate():
        db = load_genes_db()

        # ── JSON DB varsa: anlık tarama ──────────────────────────────────────
        if db:
            assemblies_db = db.get("assemblies", {})
            total = len(assemblies_db)
            yield sse({"type": "status", "message": f"JSON veritabanından {total} assembly taranıyor..."})
            yield sse({"type": "assembly_list", "total_in_ncbi": total, "to_scan": total,
                       "message": f"{total} assembly JSON'dan taranıyor."})

            found_count = 0
            items = list(assemblies_db.items())
            for idx, (accession, asm_data) in enumerate(items):
                strain_name = asm_data.get("strain", accession)
                genes = asm_data.get("genes", [])

                yield sse({"type": "scanning", "accession": accession, "strain": strain_name,
                           "progress": idx + 1, "total": total})

                # JSON'daki genlerden eşleşenleri bul
                matches = []
                query_go_ids = {q: get_go_ids_for_query(q) for q in product_queries}
                for gene in genes:
                    product  = gene.get("product", "")
                    go       = gene.get("go", "")
                    combined = f"{product} {go}".lower()
                    matched  = []
                    for q in product_queries:
                        ql = q.lower()
                        if ql in combined:
                            matched.append(q)
                        elif any(gid.lower() in go.lower() for gid in query_go_ids.get(ql, [])):
                            matched.append(q)
                    if matched:
                        matches.append({**gene, "matched_query": matched[0],
                                        "match_field": "product" if matched[0].lower() in product.lower() else "GO/note"})

                if not matches:
                    yield sse({"type": "not_found", "accession": accession, "strain": strain_name,
                               "progress": idx + 1, "total": total})
                    continue

                found_count += 1
                yield sse({
                    "type": "found", "accession": accession, "strain": strain_name,
                    "biosample": asm_data.get("biosample", ""), "taxid": asm_data.get("taxid", ""),
                    "source": "JSON DB", "match_count": len(matches), "results": matches,
                    "ncbi_url": f"https://www.ncbi.nlm.nih.gov/datasets/genome/{accession}/",
                    "progress": idx + 1, "total": total,
                })

            yield sse({"type": "done", "total_scanned": total, "found_count": found_count,
                       "skip_count": 0, "message": f"Tamamlandı: {total} strain, {found_count} pozitif."})
            return

        # ── JSON DB yoksa: NCBI'dan canlı tara (fallback) ───────────────────
        yield sse({"type": "status", "message": f"JSON DB bulunamadı, NCBI'dan taranıyor..."})
        assemblies = load_assemblies_from_tsv()
        if not assemblies:
            yield sse({"type": "error", "message": "Assembly listesi alınamadı."})
            return

        total = len(assemblies)
        yield sse({"type": "assembly_list", "total_in_ncbi": total, "to_scan": total,
                   "message": f"{total} assembly taranacak."})
        found_count = 0
        skip_count  = 0

        for idx, asm in enumerate(assemblies):
            accession   = asm["accession"]
            strain_name = asm["strain_name"]
            yield sse({"type": "scanning", "accession": accession, "strain": strain_name,
                       "progress": idx + 1, "total": total})

            ann_content, source = download_annotation(
                accession,
                ftp_refseq=asm.get("ftp_refseq", ""),
                ftp_genbank=asm.get("ftp_genbank", ""),
            )

            if ann_content is None:
                skip_count += 1
                yield sse({"type": "skip", "accession": accession, "strain": strain_name,
                           "reason": "Annotation indirilemedi", "progress": idx + 1, "total": total})
                continue

            matches = parse_annotation(ann_content, product_queries)
            if not matches:
                yield sse({"type": "not_found", "accession": accession, "strain": strain_name,
                           "progress": idx + 1, "total": total})
                continue

            found_count += 1
            yield sse({
                "type": "found", "accession": accession, "strain": strain_name,
                "biosample": asm.get("biosample", ""), "taxid": asm.get("taxid", ""),
                "source": source, "match_count": len(matches), "results": matches,
                "ncbi_url": f"https://www.ncbi.nlm.nih.gov/datasets/genome/{accession}/",
                "progress": idx + 1, "total": total,
            })

        yield sse({"type": "done", "total_scanned": total, "found_count": found_count,
                   "skip_count": skip_count,
                   "message": f"Tamamlandı: {total} strain tarandı, {found_count} pozitif."})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )


@app.route("/strain-detail", methods=["GET"])
def strain_detail():
    """Tek bir accession için detay: assembly metadata + (isteğe bağlı) gen arama."""
    accession   = request.args.get("accession", "").strip()
    product_raw = request.args.get("product", "").strip()

    if not accession:
        return jsonify({"error": "accession gerekli"}), 400

    # Assembly metadata
    meta = {}
    try:
        es = requests.get(f"{NCBI_EUTILS}/esearch.fcgi", params={
            "db": "assembly", "term": accession.split(".")[0], "retmode": "json"
        }, headers=HEADERS, timeout=(8, 15))
        ids = es.json().get("esearchresult", {}).get("idlist", [])
        if ids:
            es2 = requests.get(f"{NCBI_EUTILS}/esummary.fcgi", params={
                "db": "assembly", "id": ids[0], "retmode": "json"
            }, headers=HEADERS, timeout=(8, 15))
            doc = es2.json().get("result", {}).get(ids[0], {})
            meta = {
                "strain":       doc.get("speciesname", ""),
                "assembly_name": doc.get("assemblyname", ""),
                "status":       doc.get("assemblystatus", ""),
                "biosample":    doc.get("biosample", ""),
                "taxid":        doc.get("taxid", ""),
                "n50":          doc.get("n50", ""),
                "contig_count": doc.get("contign50", ""),
                "submissiondate": doc.get("submissiondate", ""),
            }
    except Exception as e:
        print(f"[WARN] metadata hatası: {e}")

    if not product_raw:
        return jsonify({"accession": accession, "meta": meta})

    # Gen arama
    product_queries = [p.strip() for p in product_raw.split(",") if p.strip()]
    content, source = download_annotation(accession)
    if content is None:
        return jsonify({"error": "Annotation indirilemedi", "accession": accession, "meta": meta})

    matches = parse_annotation(content, product_queries)
    return jsonify({
        "accession": accession,
        "meta":      meta,
        "source":    source,
        "matches":   matches,
        "found":     len(matches) > 0,
    })


@app.route("/protein-sequence", methods=["POST"])
def protein_sequence():
    data       = request.get_json()
    protein_id = (data or {}).get("protein_id", "").strip()
    if not protein_id:
        return jsonify({"error": "protein_id gerekli"}), 400
    seq = fetch_protein_sequence(protein_id)
    if seq:
        return jsonify({"found": True, "protein_id": protein_id, "sequence": seq})
    return jsonify({"found": False, "message": "Sekans bulunamadı."})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5051))  # DeepDive 5050 kullanıyor, biz 5051
    print(f"HalomonasScout backend http://localhost:{port} adresinde çalışıyor...")
    app.run(host="0.0.0.0", port=port, debug=False)
