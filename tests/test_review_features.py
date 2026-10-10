import json
import os
import sys
import tempfile
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import session_review
import archive
import twitch


def match(mid, outcome='Win', kills=10, shots=100, hits=50):
    return dict(match_id=mid,started_at=1000,duration_s=600,outcome=outcome,kills=kills,deaths=5,assists=3,
                shots_fired=shots,shots_hit=hits,damage_dealt=3000,damage_taken=2000,personal_score=100,max_spree=3,
                team_pscore=400,headshots=5,map='Recharge',mode='Slayer')


class ComparisonTests(unittest.TestCase):
    def test_recent_excludes_selected_and_future_sessions(self):
        sessions=[dict(start=i,matches=[match(str(i),kills=i+10)]) for i in range(8)]
        result=session_review.comparison(sessions,2,'recent')
        self.assertEqual(result['prior_count'],5)
        self.assertEqual(result['baseline']['games'],5)
        self.assertEqual(result['current']['kda'],8)
        self.assertEqual(result['baseline']['kda'],11)

    def test_squad_result_counts_match_once_accuracy_is_shot_weighted(self):
        squad=match('s');squad['members']={1:match('s',shots=100,hits=50),2:match('s',shots=300,hits=300)}
        result=session_review.comparison([dict(start=2,matches=[squad]),dict(start=1,matches=[match('b')])])
        self.assertEqual(result['current']['games'],1)
        self.assertEqual(result['current']['acc'],87.5)
        self.assertEqual(result['current']['record'],'1-0')

    def test_no_earlier_session_and_undecided_win_rate(self):
        result=session_review.comparison([dict(start=1,matches=[match('a',outcome='Tie')])])
        self.assertIsNone(result['baseline'])
        self.assertIsNone(result['current']['win_pct'])
        self.assertIsNone(session_review.comparison([]))


class ArchiveCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.folder=self.root/'session';self.folder.mkdir()
        self.file=self.folder/'test_mobile_720p60.mp4';self.file.write_bytes(b'video')
        self.sessions=self.root/'sessions.json'
        self.sessions.write_text(json.dumps({'completed':[{'id':'session','streamers':[{'name':'tester','startedAt':'2026-10-01T00:00:00Z'}]}]}))
        self.man={'sessionId':'session','source':'backfill','channels':[{'channel':'tester','filePath':'test.mkv','durationSec':7200,'startedAt':'2026-10-01T01:00:00Z'}]}
        self.write_manifest()
        self.config=patch.multiple(archive,ARCHIVE_DIR=str(self.root),SESSIONS_FILE=str(self.sessions),CHANNELS={'tester'},_duration_cache={})
        self.config.start();self.addCleanup(self.config.stop)

    def write_manifest(self):
        (self.folder/'manifest.json').write_text(json.dumps(self.man))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg tools not installed')
    def test_real_mp4_duration_overrides_manifest(self):
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=black:s=32x32:r=1',
                        '-t','70','-c:v','libx264','-pix_fmt','yuv420p','-y',str(self.file)],check=True,timeout=20)
        videos,_=archive._build()
        self.assertAlmostEqual(videos['tester'][0]['dur_s'],70,places=1)

    def test_actual_duration_limits_partial_file_coverage(self):
        with patch.object(archive,'_duration',return_value=120):
            videos,_=archive._build()
        video=videos['tester'][0]
        self.assertEqual(video['dur_s'],120)
        self.assertTrue(twitch.vod_link([video],video['start']+20,60))
        self.assertIsNone(twitch.vod_link([video],video['start']+100,30))
        self.assertIsNone(twitch.vod_link([video],video['start']-5,30))

    def test_live_recordings_use_recording_start_not_broadcast_start(self):
        self.man['source']='auto';self.write_manifest()
        with patch.object(archive,'_duration',return_value=120):
            videos,_=archive._build()
        self.assertEqual(videos['tester'][0]['start'],archive._epoch('2026-10-01T01:00:00Z'))

    def test_unknown_and_stub_durations_fail_closed(self):
        for duration in (None,23):
            with patch.object(archive,'_duration',return_value=duration):
                self.assertEqual(archive._build(),({},{}))

    def test_probe_is_cached_and_replaced_file_is_reprobed(self):
        with patch.object(archive.subprocess,'run',return_value=SimpleNamespace(stdout=json.dumps({'streams':[{'duration':'120'}],'format':{'duration':'130'}}))) as run:
            self.assertEqual(archive._duration(str(self.file)),120)
            self.assertEqual(archive._duration(str(self.file)),120)
            self.assertEqual(run.call_count,1)
            self.file.write_bytes(b'replacement video')
            archive._duration(str(self.file));self.assertEqual(run.call_count,2)

    def test_invalid_probe_duration_never_advertises_coverage(self):
        for duration in ('NaN','Infinity','0','-1','N/A'):
            with patch.object(archive,'_duration_cache',{}),patch.object(archive.subprocess,'run',return_value=SimpleNamespace(stdout=json.dumps({'streams':[{'duration':duration}]}))):
                self.assertIsNone(archive._duration(str(self.file)))

if __name__=='__main__': unittest.main()
