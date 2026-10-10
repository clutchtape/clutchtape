"""Private removal requests. No request lists or identities are exposed publicly."""
import json,os,re,secrets,threading,time
from pathlib import Path
from flask import Blueprint,abort,redirect,render_template,request
import db,privacy,capacity
from halo_paths import data_path
bp=Blueprint('data_rights',__name__)
_lock=threading.Lock()

def init():
    db.run('CREATE TABLE IF NOT EXISTS removal_requests(id TEXT PRIMARY KEY,gamertag TEXT NOT NULL,challenge TEXT NOT NULL,created REAL NOT NULL,state TEXT NOT NULL)')

def approve(rid):
    """Only called after an administrator verifies the public ownership challenge."""
    with _lock, capacity.lookup_write:
        r=db.q1("SELECT * FROM removal_requests WHERE id=? AND state='pending'",rid)
        if not r:return False
        values=[r['gamertag']]
        p=db.q1('SELECT xuid,slug FROM players WHERE gamertag=? COLLATE NOCASE',r['gamertag'])
        if p:values += [p['xuid'],p['slug']]
        # Durable policy first: a restart cannot reimport the removed identity.
        privacy.save(privacy.HASHES|{privacy.digest(x) for x in values})
        privacy.enforce()
        capacity.stats.clear();capacity.external.clear()
        db.run("UPDATE removal_requests SET state='completed',gamertag='',challenge='',created=? WHERE id=?",time.time(),rid)
        return True

def _xuid_for(gamertag):
    """Current XUID for a gamertag via the Xbox login, or None when that isn't available."""
    import asyncio,ingest,xbox
    if not xbox.status().get('connected'):return None
    try:found=asyncio.run(asyncio.wait_for(ingest.resolve_gamertag(gamertag),timeout=15))
    except Exception:return None
    return found[0] if found else None

def unblock(gamertag,xuid=''):
    """Lift a removal block. Data deleted by the removal is not restored; the next lookup re-syncs from Halo.
    Returns (lifted, message). Policy entries are anonymous hashes, so the admin names the gamertag."""
    gamertag=gamertag.strip();xuid=re.sub(r'\D','',xuid or '')
    if not gamertag and not xuid:return False,'Enter a gamertag.'
    with _lock, capacity.lookup_write:
        xuid=xuid or (_xuid_for(gamertag) if gamertag else None) or ''
        drop={privacy.digest(x) for x in (gamertag,xuid) if x}
        hit=drop&privacy.HASHES
        if not hit:return False,'That gamertag isn\u2019t blocked.'
        privacy.save(privacy.HASHES-drop)
        capacity.stats.clear();capacity.external.clear()
    note='' if xuid else ' The Xbox ID couldn\u2019t be checked (Xbox login offline), so if lookups still say unavailable, unblock again once it\u2019s back or paste the XUID.'
    return True,f'Unblocked {gamertag or xuid}. Their stats reload on the next lookup.'+note

def _pending():return db.q("SELECT * FROM removal_requests WHERE state='pending' ORDER BY created LIMIT 200")

def install(app,csrf,is_admin,client_ip):
    @bp.after_request
    def private_headers(resp):
        resp.headers['Cache-Control']='no-store';resp.headers['Referrer-Policy']='no-referrer';return resp
    @bp.route('/privacy',methods=['GET','POST'])
    def home():
        if request.method=='POST':
            csrf()
            if not capacity.limiter.allow('removal:'+client_ip(),3,86400):abort(429)
            tag=request.form.get('gamertag','').strip()
            if not re.fullmatch(r'[^\W_][\w .#\-]{0,18}',tag):return render_template('privacy.html',error='Enter a valid Halo gamertag.'),400
            if db.q1("SELECT count(*) n FROM removal_requests WHERE state='pending'")['n']>=200:abort(503)
            rid=secrets.token_urlsafe(32);challenge='CT-'+secrets.token_hex(6).upper()
            db.run('INSERT INTO removal_requests VALUES(?,?,?,?,?)',rid,tag,challenge,time.time(),'pending')
            return redirect('/privacy/request/'+rid,303)
        return render_template('privacy.html')
    @bp.get('/privacy/request/<rid>')
    def receipt(rid):
        r=db.q1('SELECT challenge,state FROM removal_requests WHERE id=?',rid)
        if not r:abort(404)
        return render_template('privacy_receipt.html',r=r)
    @bp.route('/admin/privacy',methods=['GET','POST'])
    def admin():
        if not is_admin():abort(403)
        if request.method=='POST':
            csrf()
            if request.form.get('action')=='unblock':
                ok,msg=unblock(request.form.get('gamertag',''),request.form.get('xuid',''))
                return render_template('privacy_admin.html',requests=_pending(),blocked=len(privacy.HASHES),notice=msg),200 if ok else 400
            if request.form.get('action')=='dismiss':
                db.run("UPDATE removal_requests SET state='dismissed',gamertag='',challenge='',created=? WHERE id=? AND state='pending'",time.time(),request.form.get('request',''))
                return redirect('/admin/privacy',303)
            if request.form.get('verified')!='yes':abort(400)
            if not approve(request.form.get('request','')):abort(404)
            return redirect('/admin/privacy',303)
        return render_template('privacy_admin.html',requests=_pending(),blocked=len(privacy.HASHES))
    app.register_blueprint(bp)
