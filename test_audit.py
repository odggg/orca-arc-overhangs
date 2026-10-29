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
 print('Audited execution: successful injection with all external file reads/writes denied.')
 # Directory cleanup runs after the hook; no outside opens are needed.
