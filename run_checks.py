"""Run maintained offline tests without production credentials, jobs or publishing."""
from pathlib import Path
import ast,os,subprocess,sys,shutil,tempfile
BASE=Path(__file__).resolve().parent
if __name__=='__main__':
 for path in BASE.glob('*.py'):ast.parse(path.read_text(),filename=str(path))
 failures=[]
 env=os.environ.copy()
 env['PYTHONPATH']=str(BASE)+(os.pathsep+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
 # Separate processes prevent test patches or temporary DB paths leaking between suites.
 for path in sorted((BASE/'tests').glob('test_*.py')):
  result=subprocess.run([sys.executable,str(path)],cwd=BASE,env=env)
  if result.returncode:failures.append(path.name)
 bundled_node=Path(sys.executable).parents[2]/'node/bin/node'
 system_node=shutil.which('node')
 nodes=[node for node in (bundled_node,Path(system_node) if system_node else None) if node and node.is_file()]
 if nodes:
  with tempfile.TemporaryDirectory() as folder:
   script=Path(folder)/'dashboard.js';script.write_text((BASE/'index.html').read_text().split('<script>')[1].split('</script>')[0])
   checked=False
   for node in dict.fromkeys(nodes):
    if subprocess.run([str(node),'--check',str(script)],env=env).returncode==0:
     checked=True;break
   if not checked:failures.append('dashboard JavaScript syntax')
 else:print('SKIP: JavaScript syntax check (Node unavailable).')
 print('Offline maintenance checks: '+('FAILED: '+', '.join(failures) if failures else 'PASS'),flush=True)
 raise SystemExit(bool(failures))
