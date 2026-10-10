import os,sys,unittest,tempfile,sqlite3,time,threading
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import capacity,web,db,worker,maintenance

class CapacityTests(unittest.TestCase):
    def test_single_flight_and_copy_isolation(self):
        cache=capacity.Cache();calls=[]
        def build():calls.append(1);time.sleep(.1);return {'rows':[1]}
        with ThreadPoolExecutor(max_workers=8) as pool:values=list(pool.map(lambda _:cache.get('one',60,build),range(8)))
        self.assertEqual(len(calls),1);values[0]['rows'].append(2)
        self.assertEqual(cache.get('one',60,build),{'rows':[1]})
    def test_cache_is_bounded_and_expires(self):
        cache=capacity.Cache(entries=2)
        for i in range(5):cache.get(i,10,lambda:i)
        self.assertEqual(len(cache.items),2)
        self.assertEqual(cache.get(4,-1,lambda:99),99)
    def test_limiter_is_atomic(self):
        limiter=capacity.Limiter()
        with ThreadPoolExecutor(max_workers=20) as pool:accepted=list(pool.map(lambda _:limiter.allow('one',10),range(100)))
        self.assertEqual(sum(accepted),10)
    def test_known_name_never_calls_halo(self):
        with patch.object(db,'q1',return_value={'slug':'known'}),patch('ingest.resolve_gamertag') as halo,patch('xbox.status') as xbox:
            self.assertEqual(web._add_one('Known',''),('known',None,None));halo.assert_not_called();xbox.assert_not_called()
    def test_busy_releases_no_unowned_slot(self):
        with patch.object(capacity.requests,'acquire',return_value=False),patch.object(capacity.requests,'release') as release:
            r=web.app.test_client().get('/api/live/cykul');self.assertEqual(r.status_code,503);self.assertEqual(r.headers['Retry-After'],'15');release.assert_not_called()
    def test_admin_ops_not_public(self):
        r=web.app.test_client().get('/admin/ops');self.assertEqual(r.status_code,403)
    def test_query_length_rejected(self):
        r=web.app.test_client().get('/?x='+'a'*3000);self.assertEqual(r.status_code,414)
    def test_all_worker_jobs_obey_same_cap(self):
        with patch.object(worker,'_queued',set(range(worker.MAX_PENDING))):
            self.assertFalse(worker.enqueue(999999));self.assertFalse(worker.enqueue_film(999999,['m']));self.assertFalse(worker.enqueue_detail('m'))
    def test_snapshot_contains_uncheckpointed_wal_and_restores(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.sqlite';c=sqlite3.connect(source)
            c.execute('PRAGMA journal_mode=WAL');c.execute('CREATE TABLE test (v TEXT)');c.execute("INSERT INTO test VALUES('saved during WAL')");c.commit()
            with patch.object(db,'DB_PATH',str(source)),patch.object(db,'kv_set'):
                target=maintenance.snapshot(Path(folder)/'backups')
            restored=sqlite3.connect(target);self.assertEqual(restored.execute('SELECT v FROM test').fetchone()[0],'saved during WAL');self.assertEqual(restored.execute('PRAGMA integrity_check').fetchone()[0],'ok');restored.close();c.close()
            self.assertEqual(target.stat().st_mode & 0o777,0o600)
    def test_session_html_not_shared(self):
        with patch.object(web.xbox,'status',return_value={'connected':True}):
            one=web.app.test_client().get('/about');two=web.app.test_client().get('/about')
        self.assertIn('no-store',one.headers['Cache-Control']);self.assertEqual(one.status_code,200)

if __name__=='__main__':unittest.main()

class IngestionCapacityTests(unittest.TestCase):
    def test_first_sync_yields_after_25_and_schedules_deep_history(self):
        import asyncio,ingest
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        c=sqlite3.connect(':memory:',isolation_level=None);c.row_factory=sqlite3.Row
        with patch.object(db,'conn',return_value=c):
            db.init();db.run("INSERT INTO players(id,xuid,gamertag,slug,created_at) VALUES(1,'100','Launch Test','launch-test',0)")
            calls=[]
            class Response:
                async def parse(self):return SimpleNamespace(results=[SimpleNamespace(match_id=str(i)) for i in range(25)])
            class Stats:
                async def get_match_history(self,*a,**kw):calls.append(kw);return Response()
            client=SimpleNamespace(stats=Stats())
            def row(mid):
                import re
                keys=re.findall(r':(\w+)',ingest.INSERT)
                r={k:None for k in keys};r.update(started_at=1000,duration_s=600,outcome='Win',kills=10,deaths=8,assists=3,team_pscore=100,objectives='{}');r.pop('player_id',None);r.pop('match_id',None);return mid,r
            async def match(client,sem,xuid,mid,item):return row(mid)
            with patch.object(ingest,'HaloInfiniteClient',return_value=client),patch.object(ingest.xbox,'client_args',return_value={}),patch.object(ingest,'_load_medals',new=AsyncMock()),patch.object(ingest,'_one_match',side_effect=match),patch.object(worker,'enqueue_film') as film:
                asyncio.run(ingest.sync_player(1))
            self.assertEqual(len(calls),1);self.assertEqual(db.q1('SELECT COUNT(*) n FROM matches')['n'],25)
            self.assertEqual(db.q1('SELECT sync_state FROM players')['sync_state'],'ready')
            self.assertEqual(db.kv_get('history_pending:1')['start'],25);self.assertEqual(len(film.call_args.args[1]),5)
        c.close()

class LaunchSafetyTests(unittest.TestCase):
    def test_archive_budget_released_on_close(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'video.mp4';p.write_bytes(b'x'*1024)
            with patch('archive.file_for',return_value=str(p)),patch.object(capacity.archive_streams,'acquire',return_value=True),patch.object(capacity.archive_streams,'release') as release:
                c=web.app.test_client();r=c.get('/archive/file/10000001',headers={'Range':'bytes=0-15'},buffered=False)
                self.assertEqual(r.status_code,206);self.assertEqual(r.get_data(),b'x'*16);r.close();release.assert_called_once()
    def test_archive_budget_denies_without_reading(self):
        with tempfile.NamedTemporaryFile() as f,patch('archive.file_for',return_value=f.name),patch.object(capacity.archive_streams,'acquire',return_value=False):
            self.assertEqual(web.app.test_client().get('/archive/file/10000001').status_code,503)
    def test_refresh_requires_csrf(self):
        with patch.object(worker,'enqueue') as enqueue:
            r=web.app.test_client().post('/p/cykul/refresh')
            self.assertEqual(r.status_code,400);enqueue.assert_not_called()
