"""Bounded, single-process admission and copy-on-read caches. No HTML/session caching."""
from collections import OrderedDict, deque
from copy import deepcopy
from functools import wraps
import threading
import time


class Busy(Exception):
    pass


class Cache:
    def __init__(self, entries=96, budget=64*1024*1024):
        self.entries=entries; self.budget=budget; self.items=OrderedDict(); self.flights={}; self.lock=threading.Lock(); self.bytes=0
        self.hits=0; self.misses=0

    def get(self,key,ttl,loader,stale=False):
        with self.lock:
            hit=self.items.get(key)
            if hit and time.monotonic()-hit[0]<ttl:
                self.items.move_to_end(key); self.hits+=1; value=hit[1]; event=None; owner=False
            else:
                event=self.flights.get(key); owner=event is None
                if owner:
                    event=threading.Event(); self.flights[key]=event; self.misses+=1
                value=None
        if event is None:
            return deepcopy(value)
        if not owner:
            if stale and hit:
                return deepcopy(hit[1])
            if not event.wait(2):
                raise Busy('Another request is preparing this view')
            with self.lock:
                hit=self.items.get(key)
            if hit:
                return deepcopy(hit[1])
            raise Busy('View temporarily unavailable')
        try:
            value=loader()
            size=len(repr(value))*2  # conservative string estimate + entry cap; data only
            if size<=self.budget//2:
                with self.lock:
                    old=self.items.pop(key,None)
                    if old:self.bytes-=old[2]
                    self.items[key]=(time.monotonic(),deepcopy(value),size); self.bytes+=size
                    while len(self.items)>self.entries or self.bytes>self.budget:
                        _,old=self.items.popitem(last=False);self.bytes-=old[2]
            return value
        finally:
            with self.lock:
                self.flights.pop(key,None); event.set()

    def clear(self):
        with self.lock:self.items.clear();self.bytes=0


stats=Cache()
external=Cache(256,16*1024*1024)


def memo(key,ttl=20):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            from flask import has_request_context, current_app
            if not has_request_context() or current_app.testing:
                return fn(*args,**kwargs)
            import db
            return stats.get((db.DB_PATH,fn.__module__,fn.__name__,key(*args,**kwargs)),ttl,lambda:fn(*args,**kwargs))
        return wrapped
    return decorate


class Limiter:
    def __init__(self,max_keys=10000):
        self.lock=threading.Lock();self.buckets=OrderedDict();self.max_keys=max_keys
    def allow(self,key,limit,period=60,cost=1):
        now=time.monotonic()
        with self.lock:
            q=self.buckets.get(key)
            if q is None:
                # Fail closed if attackers exhaust the key budget. Remove only expired buckets.
                for k in list(self.buckets)[:200]:
                    if not self.buckets[k] or self.buckets[k][-1]<=now-period:self.buckets.pop(k,None)
                if len(self.buckets)>=self.max_keys:return False
                q=self.buckets[key]=deque()
            while q and q[0]<=now-period:q.popleft()
            if len(q)+cost>limit:return False
            q.extend([now]*cost);return True

limiter=Limiter()
requests=threading.BoundedSemaphore(6)
lookups=threading.BoundedSemaphore(2)
lookup_write=threading.Lock()

archive_streams=threading.BoundedSemaphore(4)
