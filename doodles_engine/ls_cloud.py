"""Cloud lip-sync on the FREE Kaggle GPU (LatentSync). Usage: python ls_cloud.py <workdir>
prep -> upload private dataset -> run kernel -> wait -> download -> <workdir>/ls_out/ls_SS_LL.mp4 (+ DONE when every line came back).
Needs ~/.kaggle/access_token (or kaggle.json). Any failure exits non-zero; the caller falls back to the local mouth system."""
import json,os,re,shutil,subprocess,sys,time,glob
from pathlib import Path
HERE=Path(__file__).resolve().parent;USER='minddoodles';KERNEL='doodles-ls-run'
def log(*a):print(time.strftime('%H:%M:%S'),*a,flush=True)
def env():
    e=dict(os.environ);tp=Path.home()/'.kaggle'/'access_token'
    if tp.exists() and not e.get('KAGGLE_API_TOKEN'):
        t=tp.read_text().strip()
        if t:e['KAGGLE_API_TOKEN']=t
    return e
E=env()
def kg(*args,check=True):
    code='import sys;from kaggle.cli import main;sys.argv=["kaggle"]+sys.argv[1:];main()'
    r=subprocess.run([sys.executable,'-c',code,*args],capture_output=True,text=True,env=E)
    out=(r.stdout+r.stderr).strip()
    if check and r.returncode:raise RuntimeError(f"kaggle {' '.join(args)} failed: {out[-600:]}")
    return out
def ensure_pkg():
    r=subprocess.run([sys.executable,'-c','import kaggle'],capture_output=True,text=True,env=E)
    if r.returncode:
        log('installing kaggle package...');subprocess.run([sys.executable,'-m','pip','install','-q','kaggle'],check=True)
def main(work):
    work=Path(work).resolve();ensure_pkg()
    if not ((Path.home()/'.kaggle'/'access_token').exists() or (Path.home()/'.kaggle'/'kaggle.json').exists() or os.environ.get('KAGGLE_API_TOKEN')):
        raise SystemExit('no Kaggle token in ~/.kaggle')
    out=work/'ls_out'
    if (out/'DONE').exists():log('already done');return
    subprocess.run([sys.executable,str(HERE/'ls_prep.py'),str(work)],check=True)
    ins=work/'ls_in';jobs=json.loads((ins/'jobs.json').read_text())['jobs']
    if not jobs:raise SystemExit('no lines to lip-sync')
    slug=re.sub(r'[^a-z0-9-]+','-','doodles-ls-'+work.name.lower())[:36].strip('-')+'-'+time.strftime('%d%H%M')
    (ins/'dataset-metadata.json').write_text(json.dumps({'title':slug.replace('-',' '),'id':f'{USER}/{slug}','licenses':[{'name':'CC0-1.0'}]}))
    log('uploading',len(jobs),'lines to Kaggle (private dataset',slug,')...');print(kg('datasets','create','-p',str(ins)),flush=True)
    for i in range(60):
        s=kg('datasets','status',f'{USER}/{slug}',check=False).lower()
        if 'ready' in s:break
        time.sleep(10)
    else:raise RuntimeError('dataset never became ready: '+s)
    kd=work/'ls_kernel';kd.mkdir(exist_ok=True);shutil.copy(HERE/'ls_kernel.py',kd/'ls_kernel.py')
    (kd/'kernel-metadata.json').write_text(json.dumps({'id':f'{USER}/{KERNEL}','title':'doodles ls run','code_file':'ls_kernel.py','language':'python','kernel_type':'script','is_private':True,'enable_gpu':True,'enable_internet':True,'dataset_sources':[f'{USER}/{slug}'],'competition_sources':[],'kernel_sources':[],'model_sources':[]}))
    log('starting the free GPU...');print(kg('kernels','push','-p',str(kd)),flush=True)
    t0=time.time();last=''
    while True:
        time.sleep(45);s=kg('kernels','status',f'{USER}/{KERNEL}',check=False).lower()
        m=re.search(r'status\s+"?([a-z_.]+)',s);st=(m.group(1) if m else s[-60:])
        if st!=last:log('kaggle status:',st);last=st
        if 'complete' in s:break
        if 'error' in s or 'cancel' in s or 'fail' in s:raise RuntimeError('kernel failed: '+s[-300:])
        if time.time()-t0>5*3600:raise RuntimeError('kernel timeout')
    log('downloading results...');tmp=work/'ls_dl';shutil.rmtree(tmp,ignore_errors=True);tmp.mkdir()
    print(kg('kernels','output',f'{USER}/{KERNEL}','-p',str(tmp)),flush=True)
    out.mkdir(exist_ok=True);got=0
    for f in glob.glob(str(tmp/'**/ls_*.mp4'),recursive=True):shutil.copy(f,out/Path(f).name);got+=1
    for f in glob.glob(str(tmp/'**/*.log'),recursive=True):shutil.copy(f,out/'kaggle.log')
    shutil.rmtree(tmp,ignore_errors=True)
    if not got:raise RuntimeError('no lip-sync videos came back')
    if got==len(jobs):(out/'DONE').write_text('ok')
    log('LS_CLOUD_DONE',got,'of',len(jobs),'lines in',round((time.time()-t0)/60,1),'min')
if __name__=='__main__':main(sys.argv[1])
