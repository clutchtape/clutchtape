import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")

import db  # noqa: E402
import worker  # noqa: E402
from web import app  # noqa: E402

if __name__ == "__main__":
    db.init()
    import privacy
    privacy.enforce()
    worker.start()
    import alerts
    alerts.start()
    import maintenance
    maintenance.start()
    import streamlog                 # what each tracked channel streams, and when it switches games
    streamlog.start()
    from web import seed_featured
    seed_featured()
    # clip rubric v2 (ported from the Halo site): re-score stored film timelines once
    import threading, db as _db, ingest as _ing
    if _db.kv_get('clip_rubric') != 'halo-v7':      # v7 (2026-10-12): + game-winning finish (objective play at the end of a won close/OT game)
        def _rs():
            _ing.rescore_all(); _db.kv_set('clip_rubric', 'halo-v7')
        threading.Thread(target=_rs, name='rescore', daemon=True).start()
    else:                                            # rubric current: still load medal rarity for new films
        threading.Thread(target=_ing.refresh_rarity, name='rarity', daemon=True).start()
    from waitress import serve
    port = int(os.getenv("PORT", "8140"))
    logging.getLogger("clutchtape").info("listening on :%s", port)
    serve(app, host="0.0.0.0", port=port, threads=int(os.getenv("WEB_THREADS", "8")), connection_limit=150, channel_timeout=30, max_request_body_size=65536, max_request_header_size=16384, outbuf_overflow=512*1024)
