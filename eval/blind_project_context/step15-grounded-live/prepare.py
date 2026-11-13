"""Exact six-source Grounded preparation, no generator calls."""
import hashlib, json, os, pathlib, subprocess, urllib.request
HERE = pathlib.Path(__file__).resolve().parent
OLD = HERE.parent / 'step14-host-language-live'
WORK = pathlib.Path('/home/viadmin/.local/share/docatlas-eval/step15/work/attempt-01')
CLI = '/home/viadmin/.npm/_npx/cb869cd955fb8070/node_modules/.bin/docs-mcp-server'
LIB = 'meridian-step15-e62fa9e3'
VERSION = '1.0.0'
BASE = 'https://raw.githubusercontent.com/Vanilla1999/DocAtlas/e62fa9e357bd22731cddabe930532a4a2faecc18/eval/blind_project_context/step14-host-language-live/frozen-corpus/'
def save(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x') as f: json.dump(value,f,ensure_ascii=False,indent=2)
def main():
    os.umask(0o077)
    WORK.mkdir(parents=True,exist_ok=False)
    config = WORK/'grounded.yaml'
    config.write_text('app:\n  storePath: "'+str(WORK/'grounded-store')+'"\n  telemetryEnabled: false\n  embeddingModel: null\n')
    env = {k:v for k,v in os.environ.items() if k in ('PATH','HOME','LANG')}
    manifest=[]
    for name in ('architecture.md','calendar.md','clock.md','overview.md','reservations.md','weather.md'):
        url=BASE+name
        data=urllib.request.urlopen(url,timeout=60).read()
        assert data==(OLD/'frozen-corpus'/name).read_bytes(), name
        (HERE/'source-bytes').mkdir(exist_ok=True)
        (HERE/'source-bytes'/name).write_bytes(data)
        manifest.append(dict(path=name,url=url,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data)))
    save(HERE/'sources.json',manifest)
    for row in manifest:
        cmd=[CLI,'--config',str(config),'--telemetry=false','scrape',LIB,row['url'],'--version',VERSION,'--max-pages','1','--max-depth','0','--clean=false','--follow-redirects=false','--include-pattern',row['url'],'--output','json']
        p=subprocess.run(cmd,env=env,text=True,capture_output=True,timeout=900)
        save(HERE/'preparation'/(row['path']+'.json'),dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
        print(row['path'],p.returncode,flush=True)
        if p.returncode: raise RuntimeError('index failure; no retry')
if __name__=='__main__': main()
