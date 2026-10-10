"""Controlled cached-read load. Virtual client headers are for isolated local testing only."""
import argparse,asyncio,collections,json,statistics,time
from pathlib import Path
import aiohttp

async def run(base,rps,seconds,local=False):
    paths=['/api/live/cykul','/api/p/cykul/status','/match/0ffcad10-a648-46b1-9150-a1d56f418433?player=cykul','/live/cykul?kind=all','/p/cykul','/about','/','/squad/cykul,lethul,falcated','/live/cykul,lethul,falcated?kind=all','/history/cykul?days=all']
    values=[];codes=collections.Counter();start=time.monotonic()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20),connector=aiohttp.TCPConnector(limit=50)) as session:
        async def request(i):
            await asyncio.sleep(max(0,start+i/rps-time.monotonic()))
            t=time.monotonic()
            try:
                headers={'CF-Connecting-IP':f'198.51.100.{1+i%50}'} if local else {}
                async with session.get(base+paths[i%len(paths)],headers=headers) as r:
                    await r.read();codes[str(r.status)]+=1
            except Exception as e:codes[type(e).__name__]+=1
            values.append((time.monotonic()-t)*1000)
        await asyncio.gather(*(request(i) for i in range(int(rps*seconds))))
    values.sort();return dict(target_rps=rps,requests=len(values),seconds=round(time.monotonic()-start,2),status=dict(codes),p50_ms=round(statistics.median(values),1),p95_ms=round(values[int(len(values)*.95)-1],1),max_ms=round(max(values),1))

async def main(args):
    results=[]
    for rps in args.rates:
        result=await run(args.base,rps,args.seconds,args.local);results.append(result);print(json.dumps(result),flush=True)
    Path(args.output).write_text(json.dumps(dict(base=args.base,isolated=args.local,results=results),indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8141');p.add_argument('--rates',type=float,nargs='+',default=[5,15,30]);p.add_argument('--seconds',type=int,default=15);p.add_argument('--local',action='store_true');p.add_argument('--output',required=True);asyncio.run(main(p.parse_args()))
