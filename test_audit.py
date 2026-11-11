from pathlib import Path
import sys,tempfile
ROOT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'test-deps'),str(ROOT/'dist')]
import arc_overhang as a
from tests import fixture
with tempfile.TemporaryDirectory(dir=ROOT) as folder:
 target=Path(folder)/'audited.gcode'
 target.write_bytes(b'\xef\xbb\xbf'+fixture().encode('utf-8'))
 allowed=Path(folder).resolve()
 def audit(event,args):
  if event=='open' and args and isinstance(args[0],(str,bytes)):
   path=Path(args[0]).resolve()
   if not path.is_relative_to(allowed):
    raise PermissionError('External open denied: '+str(path))
 sys.addaudithook(audit)
 report=a.process_file(target)
 assert report['replaced_features']==1
 source=fixture()+"; CHANGE_LAYER\nG1 Z0.6\n; FEATURE: Internal solid infill\nG1 E-.8 F2100\nG1 X20 Y12 F9000\nG1 E.8 F2100\n"
 for i in range(36):
  y=12+i*.45
  xa,xb=(20,28) if i%2==0 else (28,20)
  source+=f"G1 X{xa} Y{y} F9000\nG1 X{xb} Y{y} E.3 F2400\n"
 for mode in ('arc','wave'):
  target.write_bytes(source.encode('utf-8'))
  report=a.process_file(target,{'overhang_mode':mode,'next_layer_pattern':'hilbert'})
  assert report['replaced_features']==1,report
  assert report['hilbert_features']==1,report
 print('Audited execution: Arc, Wave and Hilbert processing passed with all external file reads/writes denied.')
 # Directory cleanup runs after the hook; no outside opens are needed.
