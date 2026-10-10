import sqlite3
import unittest
from unittest.mock import patch
import db
import player_colors
import web


class PlayerColors(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:',isolation_level=None)
        self.conn.row_factory=sqlite3.Row
        self.p=patch.object(db,'conn',return_value=self.conn);self.p.start();self.addCleanup(self.p.stop);self.addCleanup(self.conn.close)
        db.init()
        db.run("INSERT INTO players(id,xuid,gamertag,slug,created_at) VALUES(1,'123','Color Test','color-test',1)")
        web.app.config.update(TESTING=True,SECRET_KEY='color-test-only')
        self.client=web.app.test_client()
        with self.client.session_transaction() as s:s['csrf']='test'

    def post(self,**data):
        return self.client.post('/p/color-test/color',data=dict(csrf='test',**data))

    def test_legacy_palette_never_exposed_or_changed(self):
        db.run("INSERT INTO player_colors VALUES(1,'#123abc',1)")
        db.run("INSERT INTO players(id,xuid,gamertag,slug,created_at) VALUES(2,'456','Private Palette Owner','private-palette-owner',1)")
        db.run("INSERT INTO player_colors VALUES(2,'#112233',1)")
        with patch.object(web.xbox,'status',return_value={'connected':True}):
            response=self.client.get('/p/color-test/color')
            about=self.client.get('/about')
        self.assertEqual(response.status_code,200)
        self.assertNotIn(b'#123abc',response.data)
        self.assertNotIn(b'Private Palette Owner',about.data)
        self.assertNotIn(b'CT_PLAYER_COLORS',about.data)
        self.assertIn(b'Save on this browser',response.data)
        self.assertEqual(self.post(color='#719bff').status_code,405)
        self.assertEqual(db.q1('SELECT color FROM player_colors WHERE player_id=1')['color'],'#123abc')

    def test_palette_validation_and_contrast(self):
        with self.assertRaises(ValueError):player_colors.palette('red; background:url(x)')
        self.assertNotEqual(player_colors.palette('#000000')['ink'],'#000000')

    def test_removed_players_cannot_be_customized(self):
        with patch.object(player_colors.privacy,'blocked',return_value=True):
            self.assertEqual(self.client.get('/p/color-test/color').status_code,404)
        self.assertFalse(db.q('SELECT * FROM player_colors'))
