#!/usr/bin/env python3
"""Pull the 'From the Archives' articles off the WordPress site into the item model."""
import re, json, html, glob, os, unicodedata, subprocess

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRAWL=os.path.join(ROOT,"crawl","stories")
OUT=os.path.join(ROOT,"data","stories.json")
IMGDIR=os.path.join(ROOT,"site","assets","stories")
os.makedirs(IMGDIR,exist_ok=True)

def slugify(s):
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode()
    return re.sub(r'-{2,}','-',re.sub(r'[^a-zA-Z0-9]+','-',s).strip('-').lower())

def txt(s):
    s=re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>','',s)
    s=re.sub(r'(?is)<figcaption[^>]*>(.*?)</figcaption>',r'\n[caption] \1\n',s)
    s=re.sub(r'(?i)<br\s*/?>','\n',s)
    s=re.sub(r'(?i)</(p|div|h[1-6]|li|figure)>','\n\n',s)
    s=re.sub(r'<[^>]+>','',s); s=html.unescape(s)
    s=s.replace('\xa0',' ').replace('’',"'").replace('‘',"'")
    s=s.replace('“','"').replace('”','"').replace('–','-').replace('—','-')
    s=re.sub(r'[ \t]+',' ',s)
    s='\n'.join(l.strip() for l in s.split('\n'))
    return re.sub(r'\n{3,}','\n\n',s).strip()

def canon(u):
    """Turn a Jetpack/Photon URL back into a plain psiu.org upload URL."""
    u=html.unescape(u).split('?')[0]
    u=re.sub(r'^https?://i[0-9]\.wp\.com/','https://',u)
    return u

def grab(url,slug,n):
    ext=os.path.splitext(url)[1].lower() or '.jpg'
    if ext not in ('.jpg','.jpeg','.png','.gif','.webp'): ext='.jpg'
    name=f"{slug}-{n}{ext}"; dest=os.path.join(IMGDIR,name)
    if not os.path.exists(dest):
        r=subprocess.run(["curl","-sfL","--max-time","60","-A","PsiU/1.0",url,"-o",dest])
        if r.returncode!=0 or os.path.getsize(dest)<600:
            if os.path.exists(dest): os.remove(dest)
            return None
    return "assets/stories/"+name

stories=[]
for f in sorted(glob.glob(os.path.join(CRAWL,'from-the-archives-*.html'))):
    h=open(f,encoding='utf-8',errors='replace').read()
    slug=os.path.basename(f)[:-5]
    sid=slugify(slug.replace('from-the-archives-',''))

    m=re.search(r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>(.*?)</h1>',h,re.S) or re.search(r'<h1[^>]*>(.*?)</h1>',h,re.S)
    title=txt(m.group(1)) if m else slug.replace('-',' ').title()
    title=re.sub(r'^From the Archives\s*[:\-–]*\s*','',title,flags=re.I).strip(' –-') or title

    dm=re.search(r'<div class="entry-content[^"]*"[^>]*>',h)
    body_html=''
    if dm:
        rest=h[dm.end():]
        end=re.search(r'(?is)<(?:footer|/article|div[^>]*class="[^"]*(?:entry-footer|post-nav|sharedaddy|ast-single-related))',rest)
        body_html=rest[:end.start()] if end else rest[:40000]

    urls=[]
    fm=re.search(r'<img[^>]*class="[^"]*wp-post-image[^"]*"[^>]*>',h)
    if fm:
        o=re.search(r'data-orig-file="([^"]+)"',fm.group(0)) or re.search(r'src="([^"]+)"',fm.group(0))
        if o: urls.append(canon(o.group(1)))
    for tag in re.findall(r'<img[^>]+>',body_html):
        o=re.search(r'data-orig-file="([^"]+)"',tag) or re.search(r'src="([^"]+)"',tag)
        if o: urls.append(canon(o.group(1)))
    seen=set(); urls=[u for u in urls if 'homepage-logo' not in u and not (u in seen or seen.add(u))]
    local=[p for p in (grab(u,sid,i+1) for i,u in enumerate(urls[:10])) if p]

    body=txt(body_html)
    body=re.sub(r'(?s)\n(Share this:|Like this:|Related|Posted in|Tags:).*$','',body).strip()
    paras=[p for p in body.split('\n\n') if len(p)>40]
    yrs=[int(y) for y in re.findall(r'\b(1[78]\d\d|19\d\d|20[0-2]\d)\b',title+' '+body[:2000])]
    stories.append(dict(id=sid,type='story',title=title,collection='stories',
        year=(min(yrs) if yrs else None),url='https://psiu.org/'+slug+'/',
        images=local,cover=(local[0] if local else None),
        lead=(paras[0][:300] if paras else ''),words=len(body.split()),body=body))

stories.sort(key=lambda s:(s['year'] or 9999))
json.dump(stories,open(OUT,'w'),indent=1)
for s in stories: print(f"{s['year'] or '????'}  {s['words']:5d}w  {len(s['images'])}img  {s['title'][:58]}")
print(len(stories),"stories ->",OUT)
