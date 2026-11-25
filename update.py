"""OpenCesta -> catálogo público FitAhorro. Sin credenciales ni datos de usuarios."""
import argparse, datetime as dt, io, json, math, pathlib, re, tarfile, urllib.request

SOURCE = 'https://github.com/ruvelro/opencesta'
LICENSE = 'https://opendatacommons.org/licenses/odbl/1-0/'
REGIONS = {'madrid': {('mercadona','mad1'),('ahorramas','madrid')}, 'barcelona':{('mercadona','bcn1')}, 'valencia':{('mercadona','vlc1')}, 'alicante':{('mercadona','alc1')}, 'general':set()}
REGIONS = {k:v|{('dia','es-default')} for k,v in REGIONS.items()}
COLS = ['chain','zone','sku','display_name','category','subcategory','unit_price','reference_price','reference_format','captured_at','brand','url']
MAX = 30_000_000

def get(url, limit=MAX):
    req=urllib.request.Request(url, headers={'User-Agent':'FitAhorro public price feed / OpenCesta attribution','Accept':'*/*'})
    with urllib.request.urlopen(req, timeout=45) as r:
        b=r.read(limit+1)
        if len(b)>limit: raise ValueError('Descarga demasiado grande')
        return b

def latest():
    data=json.loads(get('https://api.github.com/repos/ruvelro/opencesta/releases?per_page=30',2_000_000))
    releases=[]
    for r in data:
        tag=r.get('tag_name','')
        if not re.fullmatch(r'prices-\d{4}-\d{2}-\d{2}',tag) or r.get('draft') or r.get('prerelease'): continue
        for a in r.get('assets',[]):
            url=f'{SOURCE}/releases/download/{tag}/prices.tar.gz'
            if a.get('name')=='prices.tar.gz' and a.get('browser_download_url')==url: releases.append((tag[7:],url))
    if not releases: raise ValueError('No hay publicación de precios válida')
    day,url=max(releases);return day,get(url)

def positive(v):
    try: n=float(v);return round(n,4) if math.isfinite(n) and 0<n<=100000 else None
    except (TypeError,ValueError): return None

def clean(v,maxlen=300):return str(v or '').strip()[:maxlen]

def normalize(r, chain, zone, day):
    if (r['chain'],r['zone'])!=(chain,zone) or str(r['captured_at'])[:10]!=day: return None
    sku,name=clean(r['sku'],100),clean(r['display_name']);price=positive(r['unit_price'])
    if not sku or not name or price is None:return None
    ref=positive(r['reference_price']);fmt=clean(r['reference_format'],30) if ref else ''
    if not fmt:ref=None
    return {'chain':chain,'zone':zone,'sku':sku,'name':name,'category':clean(r['category']), 'subcategory':clean(r['subcategory']), 'price':price,'reference':ref,'unit':fmt,'date':day,'brand':clean(r['brand']), 'url':clean(r['url'],1000)}

def convert(blob,day,out):
    import pyarrow.parquet as pq
    day=dt.date.fromisoformat(day).isoformat()
    if day>dt.date.today().isoformat():raise ValueError('Fecha futura')
    all_rows={};counts={}
    allowed=set.union(*REGIONS.values())
    with tarfile.open(fileobj=io.BytesIO(blob),mode='r:gz') as t:
        for m in t:
            hit=re.fullmatch(r'data/chain=([a-z]+)/zone=([a-z0-9-]+)/date=(\d{4}-\d{2}-\d{2})/prices\.parquet',m.name)
            if not hit or not m.isfile():continue
            chain,zone,date=hit.groups()
            if (chain,zone) not in allowed or date!=day:continue
            if m.size>MAX:raise ValueError('Parquet demasiado grande')
            table=pq.read_table(io.BytesIO(t.extractfile(m).read()),columns=COLS)
            if not 100<=table.num_rows<=100000:raise ValueError('Tamaño de catálogo inesperado')
            valid=0
            for raw in table.to_pylist():
                row=normalize(raw,chain,zone,day)
                if row:
                    all_rows[(chain,zone,row['sku'])]=row;valid+=1
            if valid<100 or valid/table.num_rows<.8:raise ValueError('Demasiados datos inválidos')
            counts[(chain,zone)]=valid
    if not all_rows:raise ValueError('Sin precios válidos')
    # No publica una región vacía: si falta una cadena, no se inventa ni mezcla con otra fecha.
    for region,pairs in REGIONS.items():
        rows=[r for r in all_rows.values() if (r['chain'],r['zone']) in pairs]
        if not rows:raise ValueError('Región sin datos: '+region)
        payload={'schema':1,'source':'OpenCesta','source_url':SOURCE,'license':LICENSE,'date':day,'region':region,'coverage':[{'chain':c,'zone':z,'count':counts.get((c,z),0)} for c,z in sorted(pairs)],'products':rows}
        (out/f'{region}.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8')
    (out/'index.html').write_text(f'<!doctype html><meta charset=utf-8><title>FitAhorro — datos abiertos</title><h1>Datos de OpenCesta</h1><p>Captura: {day}. Conversión y selección por zona: FitAhorro. <a href="{SOURCE}">Fuente y datos originales</a> · <a href="{LICENSE}">ODbL 1.0</a>.</p><p>Acceso gratuito sin registro:</p>'+''.join(f'<p><a href="{r}.json">{r}.json</a></p>' for r in REGIONS),encoding='utf-8')
    (out/'LICENSE-DATA.txt').write_text(f'Datos de OpenCesta ({SOURCE}), ODbL 1.0 ({LICENSE}). FitAhorro convierte y selecciona campos/zonas; la base de datos derivada se ofrece con la misma licencia, libre y sin registro. Fecha de captura: {day}.',encoding='utf-8')
    print('Registros únicos:',len(all_rows),'cobertura:',counts)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=pathlib.Path);p.add_argument('--date');p.add_argument('--out',type=pathlib.Path,default=pathlib.Path('public'));a=p.parse_args()
    if a.archive:
        if not a.date:p.error('--date obligatorio con --archive')
        day,blob=a.date,a.archive.read_bytes()
    else:day,blob=latest()
    a.out.mkdir(parents=True,exist_ok=True);convert(blob,day,a.out)
