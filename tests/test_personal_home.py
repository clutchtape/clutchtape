"""Personal feed scoping, per-follow choices, game dedupe and quiet-hour delivery."""
from test_alerts import AlertTests
from unittest.mock import patch, Mock
from datetime import datetime, timezone
import json
import alerts
import db
import home_feed

class PersonalHomeTests(AlertTests):
    def test_quiet_hours_overnight_and_daylight_saving(self):
        settings=alerts.clean_settings(dict(quiet=dict(enabled=True,start='22:00',end='08:00',zone='America/New_York')))
        now=datetime(2026,11,1,3,0,tzinfo=timezone.utc).timestamp()
        self.assertEqual(alerts.quiet_until(settings,now),datetime(2026,11,1,13,0,tzinfo=timezone.utc).timestamp())
        self.assertIsNone(alerts.quiet_until(settings,datetime(2026,11,1,14,0,tzinfo=timezone.utc).timestamp()))
        for quiet in [dict(zone='fake'),dict(start='25:00'),dict(enabled=True,start='08:00',end='08:00')]:
            self.assertEqual(self.follow(quiet=quiet).status_code,400)
    def test_game_opt_in_and_per_follow_preference(self):
        f=self.follow(games=True,results=False,streams=False).json['follows'][0]
        self.match('old-game',f['since']-5000)
        self.match('new-game',f['since']+1)
        with patch.object(alerts.twitch,'enabled',return_value=False):
            alerts.collect(f['since']+500);alerts.collect(f['since']+510)
        events=db.q('SELECT payload FROM alert_events');self.assertEqual(len(events),1)
        self.assertEqual(json.loads(events[0]['payload'])['kind'],'games')
        r=self.post(self.a,'preferences',dict(targets=[f['url']],settings=dict(games=True),overrides={f['key']:dict(games=False)}))
        self.assertFalse(r.json['follows'][0]['options']['games'])
        with patch.object(alerts.twitch,'enabled',return_value=False):
            self.match('another-game',f['since']+600);alerts.collect(f['since']+1000)
        self.assertEqual(len(db.q('SELECT * FROM alert_events')),1)
    def test_quiet_keeps_inbox_and_defers_push(self):
        self.follow(streams=True,quiet=dict(enabled=True,start='00:00',end='23:59',zone='UTC'))
        self.post(self.a,'subscribe',self.sub)
        identifier=db.q1('SELECT id FROM alert_devices')['id']
        now=datetime(2026,10,9,12,0,tzinfo=timezone.utc).timestamp()
        alerts.enqueue(identifier,'stream:player_a:live',dict(kind='streams',players=['player-a'],title='Live',url='/'),now)
        with patch('pywebpush.webpush',return_value=Mock(status_code=201)) as send,patch.object(alerts.twitch,'_get',return_value=[{'id':'live'}]):
            alerts.deliver(now);send.assert_not_called()
            row=db.q1('SELECT * FROM alert_events');self.assertFalse(row['delivered']);self.assertGreater(row['next_attempt'],now)
            alerts.deliver(row['next_attempt']);self.assertEqual(send.call_count,1)
    def test_delayed_stream_alert_expires_when_broadcast_ends(self):
        self.follow();self.post(self.a,'subscribe',self.sub)
        identifier=db.q1('SELECT id FROM alert_devices')['id']
        alerts.enqueue(identifier,'stream:player_a:ended',dict(kind='streams',players=['player-a'],title='Live',url='/'),self.now-600)
        with patch.object(alerts.twitch,'_get',return_value=[]),patch('pywebpush.webpush') as send:
            alerts.deliver(self.now);send.assert_not_called()
        self.assertTrue(db.q1('SELECT delivered FROM alert_events')['delivered'])

    def test_home_only_selected_and_scoped(self):
        self.follow()
        with patch.object(home_feed,'build',return_value=[]) as build,patch.object(alerts.twitch,'enabled',return_value=False):
            r=self.post(self.a,'home',dict(targets=['/p/player-b','https://evil.example/p/player-a']))
        self.assertEqual(r.status_code,200);self.assertEqual(len(r.json['cards']),2);self.assertEqual(r.json['unavailable'],1)
        self.assertEqual(r.headers['Cache-Control'],'no-store')
        self.assertEqual(self.post(self.b,'home',dict(targets=[])).json['cards'],[])
        self.assertEqual(self.post(self.a,'home',dict(targets=['x']*21)).status_code,400)
    def test_feed_uses_real_sessions_and_reasons(self):
        f=self.follow().json['follows'][0]
        for i in range(4):self.match('loss'+str(i),self.now-i*500,outcome='Loss')
        self.match('unfinished',self.now+8000,outcome='Left')
        db.run('UPDATE matches SET ranked=1,playlist=?','Ranked Arena')
        sessions=home_feed.build(f)
        self.assertEqual(len(sessions),1);self.assertIn('4-game losing stretch to review',sessions[0]['reasons']);self.assertTrue(sessions[0]['recommended']);self.assertIn('tab=sessions',sessions[0]['url'])

    def test_home_retains_stats_review_without_video(self):
        f=self.follow().json['follows'][0]
        self.match('close-game',self.now,outcome='Win')
        db.run("UPDATE matches SET ranked=1,playlist='Ranked Arena',mode='Slayer',team_score=50,enemy_score=49")
        sessions=home_feed.build(f)
        self.assertTrue(sessions[0]['recommended'])
        self.assertIn('1 close game',sessions[0]['reasons'])
