"""2026-10-11: the sync worker's line is by priority — player syncs before match-page loads before film reads — and a
film job reads at most FILM_BATCH games before the rest go back in line."""
import asyncio,sqlite3,unittest
from unittest.mock import patch
import db,worker


class PriorityLine(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:',isolation_level=None,check_same_thread=False);self.conn.row_factory=sqlite3.Row
        self.p=patch.object(db,'conn',return_value=self.conn);self.p.start();db.init()
        self.addCleanup(self.conn.close);self.addCleanup(self.p.stop)
        while not worker._q.empty():worker._q.get_nowait()
        worker._queued.clear();worker._film_pending.clear();worker._film_rest.clear()
        self.addCleanup(worker._queued.clear)
    def drain(self):
        out=[]
        while not worker._q.empty():out.append(worker._q.get_nowait()[2])
        return out
    def test_syncs_jump_ahead_of_film_and_detail(self):
        worker.enqueue_film(7,['a','b']);worker.enqueue_detail('m1');worker.enqueue(1);worker.enqueue(2)
        self.assertEqual(self.drain(),[1,2,('detail','m1'),('film',7)])
    def test_position_counts_only_syncs_in_priority_order(self):
        worker.enqueue_film(7,['a']);worker.enqueue(1);worker.enqueue(2)
        self.assertEqual(worker.position(2),2)
    def test_film_job_reads_a_batch_and_requeues_the_rest(self):
        seen=[]
        async def fake(pid,ids):seen.append(list(ids))
        worker.enqueue_film(7,['a','b','c','d','e'])
        with patch.object(worker.ingest,'film_matches',fake):
            job=worker._q.get_nowait()[2];asyncio.run(worker._job(job))
        self.assertEqual(seen,[['a','b','c']]);self.assertEqual(worker._film_rest,{7:['d','e']})


    def test_detail_burst_preserves_sync_slots(self):
        self.assertEqual(sum(worker.enqueue_detail(str(i)) for i in range(500)), worker.MAX_DETAILS)
        self.assertTrue(worker.enqueue(100))
        self.assertEqual(worker._q.get_nowait()[2], 100)

    def test_films_cannot_fill_queue(self):
        self.assertEqual(sum(worker.enqueue_film(i, ['game']) for i in range(100)), worker.MAX_FILMS)
        self.assertTrue(worker.enqueue(1000))

    def test_secondary_jobs_respect_shared_foreground_reserve(self):
        for pid in range(worker.MAX_PENDING//2):
            worker.enqueue(pid, background=True)
        self.assertFalse(worker.enqueue_detail('blocked'))
        self.assertFalse(worker.enqueue_film(999, ['blocked']))
        self.assertTrue(worker.enqueue(1000))
