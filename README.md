# 🧂 HalomonasScout

DeepDive'dan **bağımsız** — yalnızca `Halomonas sp.` (tanımlanmamış izolatlar) için NCBI tabanlı gen tarayıcı.

## Neden ayrı bir uygulama?

DeepDive, BacDive'ı primary kaynak olarak kullanır. Ancak `Halomonas sp.` izolatlarında:
- BacDive kaydı eksik ya da `sp.` olarak etiketlenmiş kayıtlar assembly bilgisi içermiyor
- NCBI Assembly DB'de direkt `"Halomonas sp."[Organism]` ile 200+ kayıt var
- Bu uygulama doğrudan NCBI → GFF → ürün eşleşmesi zinciri kurar

## Kurulum

### Backend (Port 5051 — DeepDive'ın 5050'si ile çakışmaz)

```bash
cd backend
pip install -r requirements.txt
python backend.py
```

### Frontend

```bash
cd frontend
npm install
npm start
```

## Deploy (Render)

### Backend
1. Render'da yeni **Web Service** oluştur
2. Root: `backend/`
3. Start command: `python backend.py`
4. Port: `5051`

### Frontend
1. `frontend/src/App.js` dosyasında `API_BASE` satırını Render URL ile güncelle
2. `npm run build` → static site olarak deploy et

## Nasıl çalışır?

```
NCBI esearch: "Halomonas sp."[Organism]
    ↓
Assembly listesi (GCF/GCA accession'lar)
    ↓
Her strain için: FTP → genomic.gff.gz indir
    ↓
GFF parser: /product= alanında keyword ara
    ↓
Eşleşen genler → strain bilgisi + locus tag + protein ID
    ↓ (isteğe bağlı)
NCBI Protein → FASTA sekans
```

## Endpoints

| Endpoint | Method | Açıklama |
|---|---|---|
| `/health` | GET | Sistem durumu |
| `/count` | GET | NCBI'daki Halomonas sp. sayısı |
| `/scan?product=ectoine&retmax=100` | GET (SSE) | Paralel tarama, stream |
| `/strain-detail?accession=GCF_...&product=ectoine` | GET | Tek strain detayı |
| `/protein-sequence` | POST | FASTA sekans |

## SSE Event Tipleri

- `status` — genel bilgi mesajı
- `assembly_list` — kaç assembly taranacak
- `scanning` — şu an taranan strain
- `found` — eşleşme bulundu
- `not_found` — bu strainDE gen yok
- `skip` — annotation indirilemedi
- `done` — tamamlandı, özet

## Fark: DeepDive vs HalomonasScout

| | DeepDive | HalomonasScout |
|---|---|---|
| Kaynak | BacDive (+ NCBI fallback) | Yalnızca NCBI |
| Kapsam | Tüm bakteriler | Sadece Halomonas sp. |
| Port | 5050 | 5051 |
| BacDive bağımlılığı | ✓ | ✗ |
| sp. izolatları | Eksik | Tam kapsam |
