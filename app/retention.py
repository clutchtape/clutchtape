"""Bounded public-stat cache retention."""
import os,time
import db,capacity

def sweep(now=None):
    now=now or time.time();match_cutoff=now-180*86400;profile_cutoff=now-90*86400
    demos={s.split('|')[0].strip().casefold() for s in os.getenv('FEATURED_PLAYERS','CyKul|cykul,LethuL,Falcated').split(',')}
    with db.tx() as c:
        expired=[r['id'] for r in c.execute('SELECT id,gamertag FROM players WHERE COALESCE(last_view,created_at)<?',(profile_cutoff,)) if r['gamertag'].casefold() not in demos]
        for pid in expired:
            c.execute('DELETE FROM matches WHERE player_id=?',(pid,));c.execute('DELETE FROM moments WHERE player_id=?',(pid,));c.execute('DELETE FROM players WHERE id=?',(pid,));c.execute('DELETE FROM kv WHERE k=?',('history_pending:'+str(pid),))
        deleted=c.execute('DELETE FROM matches WHERE started_at<?',(match_cutoff,)).rowcount
        c.execute('DELETE FROM moments WHERE NOT EXISTS(SELECT 1 FROM matches m WHERE m.player_id=moments.player_id AND m.match_id=moments.match_id)')
        for table in ('events','filmed'):c.execute(f'DELETE FROM {table} WHERE match_id NOT IN(SELECT match_id FROM matches)')
        for prefix in ('matchraw:','matchdetail:','matchload:'):
            c.execute('DELETE FROM kv WHERE k LIKE ? AND substr(k,?) NOT IN(SELECT match_id FROM matches)',(prefix+'%',len(prefix)+1))
        c.execute('DELETE FROM removal_requests WHERE created<?',(now-30*86400,))
        c.execute('UPDATE players SET matches_done=(SELECT COUNT(*) FROM matches m WHERE m.player_id=players.id)')
    capacity.stats.clear();capacity.external.clear()
    result={'at':now,'profiles':len(expired),'matches':deleted};db.kv_set('ops:retention',result);return result
