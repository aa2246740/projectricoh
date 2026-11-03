"""Recreate cropped native-rate frames and their source timestamps."""
from pathlib import Path
import hashlib,json,os,plistlib,subprocess

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/diag-mount-decode-r1')
EXPECTED={'IMG_6293':'0eb0d158aa8ca92e29306022d3ef00747c33bdc2da95cb8a72b9f68b3e0369e1',
          'IMG_6294':'16a2c852ec2d644b3f9e8bb95d38edb006a3f4b52f2ab74b469cddf17c7b950d'}

def main():
    subprocess.run(['df','-h','/Volumes/Workspace'],check=True)
    info=plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
    assert info['FilesystemType']=='apfs' and info['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and info['WritableVolume']
    TMP.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,TMPDIR=str(TMP),PYTHONDONTWRITEBYTECODE='1')
    for video,expected in EXPECTED.items():
        media=ROOT/'captures/diag-v4p-mount-20261102'/(video+'.MOV')
        assert hashlib.sha256(media.read_bytes()).hexdigest()==expected
        target=TMP/video;target.mkdir(exist_ok=True)
        assert not list(target.glob('frame-*.jpg')), 'frame directory must be empty'
        result=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
            '-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',str(media)],env=env,timeout=180))
        frames=[dict(frame=i+1,seconds=float(f['best_effort_timestamp_time'])) for i,f in enumerate(result['frames'])]
        (HERE/(video+'-timestamps.json')).write_text(json.dumps(frames,indent=2)+'\n')
        subprocess.run(['ffmpeg','-v','error','-nostdin','-threads','2','-i',str(media),'-map','0:v:0',
                        '-vf','crop=800:1420:0:430','-fps_mode','passthrough','-q:v','2',str(target/'frame-%05d.jpg')],
                       env=env,check=True,timeout=180)
        assert len(list(target.glob('frame-*.jpg')))==len(frames)
        (TMP/(video+'-ocr-list.txt')).write_text(''.join(str(target/('frame-%05d.jpg'%f['frame']))+'\n' for f in frames if f['frame']%4==1))
        print(video,len(frames))

if __name__=='__main__':main()
