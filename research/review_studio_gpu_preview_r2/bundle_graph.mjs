import {writeFileSync} from 'node:fs';
import {build} from '/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview/frontend/node_modules/vite/dist/node/index.js';
const wt='/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview';
process.chdir(wt+'/frontend');
const chunks=[];
await build({root:wt+'/frontend',configFile:wt+'/frontend/vite.config.ts',build:{outDir:'/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r2/graph-build'},plugins:[{name:'independent-review-module-graph',generateBundle(_options,bundle){for(const [fileName,item]of Object.entries(bundle))if(item.type==='chunk')chunks.push({fileName,imports:item.imports,dynamicImports:item.dynamicImports,modules:item.moduleIds});}}]});
writeFileSync(new URL('bundle-module-graph.json',import.meta.url),JSON.stringify(chunks,null,2)+'\n');
console.log(JSON.stringify(chunks));
