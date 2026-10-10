import sys,sqlite3,unittest,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import privacy,db,web,match_detail,ingest

class PrivacyTests(unittest.TestCase):
    def test_normalized_removal_avoids_reimport(self):
        with patch.object(privacy,'HASHES',{privacy.digest('Example Private User')}),patch.object(ingest,'resolve_gamertag') as resolve:
            self.assertTrue(privacy.blocked('example-private-user'))
            self.assertEqual(web._add_one('Example Private User',''),(None,None,'This profile is unavailable.'));resolve.assert_not_called()
    def test_roster_excludes_removed_identity(self):
        from test_match_detail import fixture
        with patch.object(privacy,'HASHES',{privacy.digest('5678')}):
            detail=match_detail.normalize(fixture(),{'1234':'Public','5678':'Example Private User'},{})
        self.assertEqual([p['name'] for p in detail['players']],['Public'])
    def test_removal_clears_profile_games_films_and_cache(self):
        c=sqlite3.connect(':memory:',isolation_level=None);c.row_factory=sqlite3.Row
        with patch.object(db,'conn',return_value=c),patch.object(privacy,'HASHES',{privacy.digest('12345')}):
            db.init();db.run("INSERT INTO players(id,xuid,gamertag,slug,created_at) VALUES(1,'12345','Example Private User','example-private-user',0)")
            db.run("INSERT INTO matches(player_id,match_id,started_at) VALUES(1,'remove-game',1)")
            db.run("INSERT INTO events VALUES('remove-game','12345','Example Private User',1,'kill',NULL)")
            db.run("INSERT INTO filmed VALUES('remove-game',1,1)");db.kv_set('matchdetail:remove-game',{'players':[]})
            privacy.enforce()
            for table in ['players','matches','events','filmed']:self.assertEqual(db.q1('SELECT COUNT(*) n FROM '+table)['n'],0)
            self.assertIsNone(db.kv_get('matchdetail:remove-game'))
        c.close()
