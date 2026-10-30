"""Small offline card replay page; no new server, model or video rendering.

Pass a saved EXP-0036 JSON and optionally an existing comparison MP4.
All notifications here are playback-demo toasts, not production alerts.
"""
import argparse
import html
import json
import os
from pathlib import Path
from urllib.parse import quote


def write_preview(bundle_path, output, media=None):
    src, dst = Path(bundle_path), Path(output)
    bundle = json.loads(src.read_text(encoding='utf-8'))
    if bundle.get('experiment') != 'EXP-0036':
        raise ValueError('An EXP-0036 bundle is required')
    if (dst.exists() or dst.is_symlink() or any(p.is_symlink() for p in dst.parents)
            or not dst.resolve().is_relative_to(Path('outputs').resolve())):
        raise ValueError('Use a NEW non-symlink HTML under outputs/')
    media_attr = ''
    if media is not None:
        media = Path(media)
        if not media.is_file():
            raise ValueError('Existing local comparison MP4 required')
        url = quote(os.path.relpath(media.resolve(), dst.parent.resolve()).replace(os.sep,'/'),safe='/')
        media_attr = ' src="' + html.escape(url,quote=True) + '"'
    payload = json.dumps(bundle, ensure_ascii=False, allow_nan=False).replace('<','\\u003c')
    page = r'''<!doctype html><html lang="ko"><meta charset="utf-8">
<title>SceneGuard 침입 알림</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{font:16px system-ui,sans-serif;max-width:1080px;margin:30px auto;padding:0 20px;background:#f6f8fb;color:#162536}video{width:100%;max-height:500px;background:#111}article{padding:18px;margin:12px 0;background:white;border:1px solid #ccd4df;border-radius:10px}h1{font-size:26px}h2{font-size:20px;margin:0 0 10px}p{line-height:1.6}input[type=range]{width:100%}#toast{position:fixed;bottom:20px;right:20px;background:#162536;color:white;padding:15px;display:none}button{padding:8px 14px;cursor:pointer}small{color:#46566b}</style>
<h1>SceneGuard · 침입 알림</h1>
<p>같은 출입구의 반복 알림은 하나의 카드로 표시합니다. 인원 수나 침입 확정을 의미하지 않습니다.</p>
<video id="video" controls preload="metadata"__MEDIA__></video>
<p><label>기존 비교 영상 선택 <input id="file" type="file" accept="video/*"></label></p>
<label>원본 시각 <output id="clock"></output><input id="time" type="range" step="0.001"></label>
<p id="counter"></p><p><small>저장 결과의 재생 데모입니다. 이동/되감기와 새로고침에서는 알림을 반복하지 않습니다.</small></p>
<div id="cards"></div><div id="toast" role="status"></div>
<script id="data" type="application/json">__DATA__</script>
<script>
'use strict';
const data=JSON.parse(document.getElementById('data').textContent);
const video=document.getElementById('video'), slider=document.getElementById('time');
const [start,end]=data.source_window; slider.min=start;slider.max=end;slider.value=start;
const storageKey='sceneguard36:'+data.video_id+':'+(data.provenance?.source_sha256||'preview');
let notified;try{notified=new Set(JSON.parse(sessionStorage.getItem(storageKey)||'[]'));}catch(e){notified=new Set();}
let previous=start, toastTimer, objectUrl=null;
const byId=new Map(data.events.map(e=>[e.event_id,e]));
function saveSeen(){try{sessionStorage.setItem(storageKey,JSON.stringify([...notified]));}catch(e){}}
function update(pts, notify=false){
 const snapshots=new Map();let raw=0;
 for(const item of data.timeline){
  if(item.decision_time_pts>pts+1e-9)continue;
  if(item.action==='duplicate')continue;
  snapshots.set(item.incident_id,item.card);raw++;
  if(item.notify){
   const fresh=!notified.has(item.notification_key);
   notified.add(item.notification_key);
   if(notify&&fresh&&item.decision_time_pts>previous+1e-9){
    const toast=document.getElementById('toast');toast.textContent='침입 의심 · '+item.card.gate_id;
    toast.style.display='block';clearTimeout(toastTimer);toastTimer=setTimeout(()=>toast.style.display='none',2000);
   }
  }
 }
 saveSeen();previous=pts;slider.value=pts;
 document.getElementById('clock').textContent=pts.toFixed(3)+'초';
 document.getElementById('counter').textContent='개별 알림 '+raw+'개 → 사건 카드 '+snapshots.size+'개';
 const list=document.getElementById('cards');list.replaceChildren();
 for(const card of snapshots.values()){
  const a=document.createElement('article'),h=document.createElement('h2'),p=document.createElement('p');
  h.textContent=card.status+' · '+card.gate_id;
  p.textContent=card.first_alert_pts.toFixed(3)+'~'+card.last_alert_pts.toFixed(3)+'초 | 관련 알림 '+card.alert_count+'개 | 추적 ID '+card.track_ids.join(', ');
  const btn=document.createElement('button');btn.textContent='근거 시점 보기';
  btn.onclick=()=>{const t=Math.max(start,card.first_alert_pts-3);video.pause();video.currentTime=t-start;update(t,false);};
  const detail=document.createElement('details'),sum=document.createElement('summary'),pre=document.createElement('pre');
  sum.textContent='원래 알림 보기';pre.style.whiteSpace='pre-wrap';
  pre.textContent=card.event_ids.map(id=>{const e=byId.get(id);return e.decision_time_pts.toFixed(3)+'초 | '+e.source_ref.collection+' | ID '+e.track_ids.join(', ');}).join('\n');
  detail.append(sum,pre);a.append(h,p,btn,detail);list.append(a);
 }
}
slider.oninput=()=>{video.pause();const t=Number(slider.value);if(video.currentSrc)video.currentTime=t-start;update(t,false);};
video.onseeking=()=>update(Math.min(end,start+video.currentTime),false);
video.ontimeupdate=()=>update(Math.min(end,start+video.currentTime),!video.seeking&&!video.paused);
document.getElementById('file').onchange=e=>{const f=e.target.files[0];if(!f)return;if(objectUrl)URL.revokeObjectURL(objectUrl);objectUrl=URL.createObjectURL(f);video.src=objectUrl;previous=start;update(start,false);};
update(start,false);
</script></html>'''.replace('__MEDIA__',media_attr).replace('__DATA__',payload)
    dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open('x',encoding='utf-8') as stream:
        stream.write(page)
    return dst


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--media',type=Path)
    a=p.parse_args()
    print(write_preview(a.bundle,a.output,a.media))


if __name__=='__main__':main()
