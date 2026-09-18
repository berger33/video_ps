#!/usr/bin/env python3
from pathlib import Path
import subprocess,json
ROOT=Path(__file__).resolve().parents[1]; S=ROOT/'assets/source'; O=ROOT/'assets/prepared_color'; M=O/'masks'; R=O/'rgba'
def run(*a): subprocess.run([str(x) for x in a],check=True)
def main():
 M.mkdir(parents=True,exist_ok=True); R.mkdir(parents=True,exist_ok=True)
 for n in (1,2,3):
  p=S/f'capybara_pose_{n:02d}.png'; m=M/p.name; r=R/p.name
  run('convert',p,'-alpha','off','-fuzz','18%','-transparent','#00ff00','-alpha','extract','-blur','0x0.45',m)
  run('convert',p,m,'-alpha','off','-compose','CopyOpacity','-composite',r)
 (O/'manifest.json').write_text(json.dumps({'source_frames':3,'dimensions':'1376x768','method':'per-frame chroma key #00ff00, fuzz 18%, edge blur 0.45px','cycle':['pose_01','pose_02','pose_03','pose_02']},indent=2)+'\n')
if __name__=='__main__': main()
