"""
preparse.py — HalomonasScout Pre-Parser
Tüm Halomonas sp. assembly'lerini tara, gen tablosunu JSON olarak kaydet.
Bu JSON GitHub'a konulacak, site bu dosyadan arayacak.

Kullanım:
    python preparse.py

Çıktı:
    halomonas_genes.json
"""

import json, os, sys, time
from backend import (
    load_assemblies_from_tsv,
    download_annotation,
    parse_annotation,
)

OUT_FILE = "halomonas_genes.json"

def main():
    print("=" * 60)
    print("HalomonasScout Pre-Parser")
    print("=" * 60)

    assemblies = load_assemblies_from_tsv()
    if not assemblies:
        print("HATA: TSV yüklenemedi!")
        sys.exit(1)

    print(f"{len(assemblies)} assembly taranacak\n")

    # Tüm genleri topla
    # Yapı: { accession: { strain, genes: [...] } }
    all_genes = {}
    skipped   = []
    total     = len(assemblies)

    for i, asm in enumerate(assemblies):
        acc         = asm["accession"]
        strain_name = asm["strain_name"]
        pct         = int((i + 1) / total * 100)

        print(f"[{i+1}/{total}] {pct}% | {acc} | {strain_name}")

        content, source = download_annotation(
            acc,
            ftp_refseq=asm.get("ftp_refseq", ""),
            ftp_genbank=asm.get("ftp_genbank", ""),
        )

        if content is None:
            print(f"  ⊘ Atlandı: annotation indirilemedi")
            skipped.append(acc)
            continue

        # Tüm CDS genlerini çek — boş query ile tüm product'ları al
        genes = parse_all_genes(content)
        print(f"  ✓ {len(genes)} gen")

        all_genes[acc] = {
            "strain":    strain_name,
            "accession": acc,
            "biosample": asm.get("biosample", ""),
            "taxid":     asm.get("taxid", ""),
            "status":    asm.get("assembly_status", ""),
            "source":    source,
            "genes":     genes,
        }

        # Her 10 assembly'de bir kaydet (crash protection)
        if (i + 1) % 10 == 0:
            _save(all_genes, skipped, total)
            print(f"  → Ara kayıt yapıldı ({len(all_genes)} assembly)")

    # Final kayıt
    _save(all_genes, skipped, total)
    print("\n" + "=" * 60)
    print(f"TAMAMLANDI!")
    print(f"  Taranan  : {len(all_genes)}")
    print(f"  Atlandı  : {len(skipped)}")
    print(f"  Çıktı    : {OUT_FILE}")
    print("=" * 60)


def parse_all_genes(content: str) -> list[dict]:
    """Tüm CDS genlerini çek (product alanı olan her şey)."""
    import re, urllib.parse

    genes = []

    # GBFF mi GFF mi?
    if content and "LOCUS" in content[:500] and "FEATURES" in content:
        # GBFF parser
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
                if current_feature in ("CDS", "gene") and current_attrs.get("product"):
                    genes.append(_make_gene(current_attrs, current_contig, current_location, current_feature))
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
        # Son feature
        if current_feature in ("CDS", "gene") and current_attrs.get("product"):
            genes.append(_make_gene(current_attrs, current_contig, current_location, current_feature))
    else:
        # GFF parser
        for line in content.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 9:
                continue
            contig, _, feat_type, start, stop, _, strand, _, attrs = parts[:9]
            if feat_type not in ("CDS", "gene"):
                continue
            attr_dict = {}
            for attr in attrs.split(";"):
                if "=" in attr:
                    k, v = attr.split("=", 1)
                    attr_dict[k.strip()] = urllib.parse.unquote(v.strip())
            product = attr_dict.get("product", "")
            if not product:
                continue
            go_func = attr_dict.get("Dbxref", "")
            genes.append({
                "locus_tag":  attr_dict.get("locus_tag", ""),
                "gene":       attr_dict.get("gene", ""),
                "product":    product,
                "protein_id": attr_dict.get("protein_id", ""),
                "contig":     contig,
                "start":      start,
                "stop":       stop,
                "strand":     strand,
                "type":       feat_type,
                "go":         go_func,
            })
    return genes


def _make_gene(attrs, contig, location, feat_type):
    import re
    strand = "-" if "complement" in location else "+"
    coords = re.findall(r'\d+', location)
    go_func = attrs.get("GO_function", "") + " " + attrs.get("GO_process", "")
    return {
        "locus_tag":  attrs.get("locus_tag", ""),
        "gene":       attrs.get("gene", ""),
        "product":    attrs.get("product", ""),
        "protein_id": attrs.get("protein_id", ""),
        "contig":     contig,
        "start":      coords[0] if coords else "",
        "stop":       coords[-1] if len(coords) > 1 else "",
        "strand":     strand,
        "type":       feat_type,
        "go":         go_func.strip(),
    }


def _save(all_genes, skipped, total):
    out = {
        "meta": {
            "total_assemblies": total,
            "parsed":           len(all_genes),
            "skipped":          len(skipped),
            "skipped_list":     skipped,
            "generated_at":     time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "assemblies": all_genes,
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    size_mb = os.path.getsize(OUT_FILE) / 1024 / 1024
    print(f"  💾 {OUT_FILE} kaydedildi ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
