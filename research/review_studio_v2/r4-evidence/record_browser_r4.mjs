import {execFileSync} from 'node:child_process';
import {writeFile} from 'node:fs/promises';
const root='/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r4';
export async function recordBrowser(name){
 const lines=execFileSync('/bin/ps',['-axo','pid=,ppid=,command='],{encoding:'utf8'}).split(String.fromCharCode(10));
 const ours=lines.filter(s=>s.includes('chrome-headless-shell')&&s.includes('--user-data-dir=')&&Number(s.trim().split(/\s+/)[1])===process.pid);
 if(ours.length!==1)throw Error('Expected exactly one test browser: '+JSON.stringify(ours));
 const profile=ours[0].match(/--user-data-dir=([^ ]+)/)?.[1];
 if(!profile?.startsWith(root+'/'))throw Error('Browser profile outside Scratch: '+profile);
 await writeFile(root+'/evidence/browser-'+name+'.json',JSON.stringify({nodePid:process.pid,userDataDir:profile,command:ours[0].trim()},null,2)+String.fromCharCode(10));
}
