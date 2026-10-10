"""Private review rooms: local accounts, expiring invitations and membership checks."""
import hashlib, hmac, re, secrets, time
from urllib.parse import urlsplit, parse_qs, urlencode
from flask import Blueprint, abort, redirect, render_template, request, session, g
from werkzeug.security import generate_password_hash, check_password_hash
import db
bp=Blueprint('rooms',__name__)
DUMMY=generate_password_hash('not-a-real-password')
SCHEMA='''
CREATE TABLE IF NOT EXISTS review_users(id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, password TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS review_sessions(token TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS review_rooms(id TEXT PRIMARY KEY, name TEXT NOT NULL, owner TEXT NOT NULL, created REAL NOT NULL, invite_hash TEXT, invite_until REAL);
CREATE TABLE IF NOT EXISTS review_members(room_id TEXT NOT NULL, user_id TEXT NOT NULL, PRIMARY KEY(room_id,user_id));
CREATE TABLE IF NOT EXISTS review_posts(id TEXT PRIMARY KEY, room_id TEXT NOT NULL, user_id TEXT NOT NULL, parent TEXT, body TEXT NOT NULL, url TEXT, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS review_posts_room ON review_posts(room_id,created);
CREATE TABLE IF NOT EXISTS review_limits(bucket TEXT NOT NULL, at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS review_limits_bucket ON review_limits(bucket,at);
'''

def init(): db.conn().executescript(SCHEMA)
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def user():
    token=session.get('review_token','')
    return db.q1('SELECT u.* FROM review_users u JOIN review_sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?',digest(token),time.time()) if token else None

def require_user():
    u=user()
    if not u: abort(401,'Sign in from Squad rooms to continue. Your room has not been changed.')
    return u

def member(rid):
    u=require_user()
    room=db.q1('SELECT r.* FROM review_rooms r JOIN review_members m ON m.room_id=r.id WHERE r.id=? AND m.user_id=?',rid,u['id'])
    if not room: abort(404)
    return u,room

def limit(bucket,maximum=20):
    now=time.time()
    with db.tx():
        db.run('DELETE FROM review_limits WHERE at<?',now-3600)
        n=db.q1('SELECT COUNT(*) n FROM review_limits WHERE bucket=?',bucket)['n']
        if n>=maximum: abort(429,'Too many attempts. Please try again in an hour.')
        db.run('INSERT INTO review_limits VALUES(?,?)',bucket,now)

def moment_url(raw):
    """Only same-site canonical game review links, never arbitrary shared URLs."""
    try: u=urlsplit(raw.strip())
    except ValueError: return None
    if u.netloc and u.netloc!=request.host: return None
    if u.scheme and u.scheme not in ('http','https'): return None
    if not re.fullmatch(r'/live/[a-z0-9,-]+',u.path): return None
    args=parse_qs(u.query);mid=args.get('match',[''])[0]
    if not re.fullmatch(r'[a-fA-F0-9-]{36}',mid): return None
    slugs=u.path.split('/')[-1].split(',')
    if not 1<=len(slugs)<=4: return None
    for slug in slugs:
        if not db.q1('SELECT 1 FROM matches m JOIN players p ON p.id=m.player_id WHERE p.slug=? AND m.match_id=?',slug,mid): return None
    try: at=max(0,min(86400,int(args.get('at',['0'])[0])))
    except ValueError: return None
    kind=args.get('kind',['mm'])[0]
    if kind not in ('mm','ranked','custom','all'): kind='mm'
    return u.path+'?'+urlencode(dict(kind=kind,match=mid,at=at))+'#recap'

def install(app,csrf,ip):
    @bp.before_request
    def protect():
        if request.method=='POST': csrf()

    @bp.after_request
    def private_headers(resp):
        resp.headers['Cache-Control']='no-store'
        resp.headers['Referrer-Policy']='no-referrer'
        return resp

    @app.context_processor
    def account_context(): return {'review_user':user()}

    @bp.route('/rooms',methods=['GET','POST'])
    def home():
        u=user()
        if request.method=='POST':
            u=require_user();limit('create:'+u['id'],10)
            name=request.form.get('name','').strip()
            if not 1<=len(name)<=80: abort(400,'Room names must be 1–80 characters.')
            rid=secrets.token_urlsafe(18)
            with db.tx():
                db.run('INSERT INTO review_rooms(id,name,owner,created) VALUES(?,?,?,?)',rid,name,u['id'],time.time())
                db.run('INSERT INTO review_members VALUES(?,?)',rid,u['id'])
            return redirect('/rooms/'+rid,303)
        rs=db.q('SELECT r.* FROM review_rooms r JOIN review_members m ON m.room_id=r.id WHERE m.user_id=? ORDER BY r.created DESC',u['id']) if u else []
        return render_template('rooms.html',u=u,rooms=rs)

    @bp.route('/account',methods=['POST'])
    def account():
        limit('auth-ip:'+digest(ip()),30)
        name=request.form.get('name','').strip().lower();password=request.form.get('password','');action=request.form.get('action')
        if not re.fullmatch(r'[a-z0-9_-]{3,32}',name) or not 12<=len(password)<=128:
            return render_template('rooms.html',u=None,rooms=[],error='Use a 3–32 character username (letters, numbers, _ or -) and a 12–128 character password.'),400
        limit('auth-name:'+digest(name),15)
        u=db.q1('SELECT * FROM review_users WHERE name=?',name)
        if action=='register':
            if u: return render_template('rooms.html',u=None,rooms=[],error='That username is unavailable. Choose another or sign in.'),400
            uid=secrets.token_urlsafe(18)
            import sqlite3
            try: db.run('INSERT INTO review_users VALUES(?,?,?,?)',uid,name,generate_password_hash(password),time.time())
            except sqlite3.IntegrityError: abort(409,'That username is unavailable.')
        elif action=='login':
            if not check_password_hash(u['password'] if u else DUMMY,password) or not u:
                return render_template('rooms.html',u=None,rooms=[],error='Username or password was not recognized.'),400
            uid=u['id']
        else: abort(400)
        if session.get('review_token'): db.run('DELETE FROM review_sessions WHERE token=?',digest(session['review_token']))
        session.pop('csrf',None)
        token=secrets.token_urlsafe(32);session['review_token']=token
        db.run('DELETE FROM review_sessions WHERE expires<?',time.time())
        db.run('INSERT INTO review_sessions VALUES(?,?,?)',digest(token),uid,time.time()+7*86400)
        return redirect('/rooms',303)

    @bp.route('/account/logout',methods=['POST'])
    def logout():
        db.run('DELETE FROM review_sessions WHERE token=?',digest(session.pop('review_token','')))
        session.pop('csrf',None)
        return redirect('/rooms',303)

    @bp.route('/rooms/<rid>',methods=['GET','POST'])
    def room(rid):
        u,r=member(rid)
        if request.method=='POST':
            limit('post:'+u['id'],60)
            body=request.form.get('body','').strip();raw=request.form.get('url','').strip();parent=request.form.get('parent') or None
            if not 1<=len(body)<=2000: abort(400,'Write a note of 1–2000 characters.')
            url=moment_url(raw) if raw else None
            if raw and not url: abort(400,'Use a Clutchtape game moment link from the event timeline.')
            if parent and not db.q1('SELECT 1 FROM review_posts WHERE id=? AND room_id=? AND parent IS NULL',parent,rid): abort(404)
            with db.tx():
                # Recheck inside the write transaction: a removed member cannot race a post.
                member(rid)
                db.run('INSERT INTO review_posts VALUES(?,?,?,?,?,?,?)',secrets.token_urlsafe(18),rid,u['id'],parent,body,url,time.time())
            return redirect('/rooms/'+rid+'#discussion',303)
        posts=db.q('SELECT p.*,u.name FROM review_posts p JOIN review_users u ON u.id=p.user_id WHERE p.room_id=? ORDER BY p.created',rid)
        members=db.q('SELECT u.id,u.name FROM review_members m JOIN review_users u ON u.id=m.user_id WHERE m.room_id=? ORDER BY u.name',rid)
        return render_template('room.html',u=u,room=r,posts=posts,members=members,invite=None)

    @bp.route('/rooms/<rid>/manage',methods=['POST'])
    def manage(rid):
        u,r=member(rid)
        if u['id']!=r['owner']: abort(403)
        action=request.form.get('action')
        if action=='invite':
            token=secrets.token_urlsafe(32)
            db.run('UPDATE review_rooms SET invite_hash=?,invite_until=? WHERE id=?',digest(token),time.time()+86400,rid)
            return render_template('invite.html',room=r,invite=request.host_url.rstrip('/')+'/join/'+rid+'/'+token)
        if action=='revoke': db.run('UPDATE review_rooms SET invite_hash=NULL,invite_until=NULL WHERE id=?',rid)
        elif action=='remove':
            uid=request.form.get('user')
            if uid==u['id']: abort(400)
            db.run('DELETE FROM review_members WHERE room_id=? AND user_id=?',rid,uid)
        elif action=='delete':
            with db.tx():
                db.run('DELETE FROM review_posts WHERE room_id=?',rid)
                db.run('DELETE FROM review_members WHERE room_id=?',rid)
                db.run('DELETE FROM review_rooms WHERE id=?',rid)
            return redirect('/rooms',303)
        elif action!='revoke': abort(400)
        return redirect('/rooms/'+rid,303)

    @bp.route('/join/<rid>/<token>',methods=['GET','POST'])
    def join(rid,token):
        r=db.q1('SELECT * FROM review_rooms WHERE id=?',rid)
        if not r or not r['invite_hash'] or not hmac.compare_digest(r['invite_hash'],digest(token)) or (r['invite_until'] or 0)<time.time(): abort(404,'This invitation is expired or revoked. Ask the owner for a new link.')
        u=user()
        if request.method=='POST':
            u=require_user()
            with db.tx():
                r=db.q1('SELECT * FROM review_rooms WHERE id=?',rid)
                if not r or not r['invite_hash'] or not hmac.compare_digest(r['invite_hash'],digest(token)) or r['invite_until']<time.time(): abort(404)
                db.run('INSERT OR IGNORE INTO review_members VALUES(?,?)',rid,u['id'])
            return redirect('/rooms/'+rid,303)
        return render_template('join.html',u=u,room=r)
    app.register_blueprint(bp)
