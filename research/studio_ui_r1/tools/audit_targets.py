"""可点元素尺寸审计：给每张设计稿注入测量脚本（副本放临时目录），用无界面 Chrome --dump-dom 读结果。
用法：python3 -I tools/audit_targets.py   （结果打印到标准输出）"""
import html, os, pathlib, re, subprocess

R = pathlib.Path(__file__).resolve().parents[1]
S = pathlib.Path("/Volumes/Workspace/Scratch/tmp/projectricoh/studio-ui-design-r1")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
JS = r"""<script>addEventListener("load",()=>{
const sel="button,a,input,select,[role=button],[role=switch],[role=slider],.select,.tile,.fcard,.cell,.fthumb,.sidebar .it,.menu .it,.cardchip";
const out=[];let n=0;
for(const el of document.querySelectorAll(sel)){const r=el.getBoundingClientRect();const st=getComputedStyle(el);
 if(!r.width||!r.height||st.visibility==="hidden"||st.display==="none")continue;
 if(r.bottom<0||r.top>innerHeight||r.right<0||r.left>innerWidth)continue;
 if(el.closest(".scrim")===null&&document.querySelector(".scrim")&&!el.closest(".dialog"))continue;
 n++;if(r.width<28||r.height<28)out.push(el.tagName.toLowerCase()+"."+[...el.classList].join(".")+" "+Math.round(r.width)+"x"+Math.round(r.height)+" "+(el.getAttribute("title")||el.getAttribute("aria-label")||el.textContent||"").trim().slice(0,16));}
const p=document.createElement("pre");p.id="audit";p.textContent="TOTAL "+n+String.fromCharCode(10)+out.join(String.fromCharCode(10));document.body.append(p);});</script>"""

def main() -> None:
    (S / "audit").mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TMPDIR=str(S / "tmp"))
    for f in sorted((R / "screens").glob("[0-9]*.html")):
        src = f.read_text().replace("<head>", f'<head><base href="file://{R}/screens/">', 1).replace("</body>", JS + "</body>", 1)
        dst = S / "audit" / f.name
        dst.write_text(src)
        dom = subprocess.run([CHROME, "--headless=new", f"--user-data-dir={S / 'chrome'}", "--no-first-run", "--disable-extensions",
                              "--window-size=1728,1117", "--virtual-time-budget=2500", "--dump-dom", f"file://{dst}"],
                             capture_output=True, text=True, env=env, timeout=60).stdout
        m = re.search(r'<pre id="audit">(.*?)</pre>', dom, re.S)
        res = html.unescape(m.group(1)).strip() if m else "NO RESULT"
        for line in res.splitlines():
            print(f"{f.stem}: {line}")

if __name__ == "__main__":
    main()
