// 用真实汇总模块核对后端收据会呈现出的状态文字。
import fs from 'node:fs';
import vm from 'node:vm';

const out = '/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_a1a_r2';
const source = '/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/web/assets/import_summary.js';
const module = new vm.SourceTextModule(fs.readFileSync(source, 'utf8'));
await module.link(() => {throw new Error('unexpected module');});
await module.evaluate();
const records = JSON.parse(fs.readFileSync(out + '/observations-final.json', 'utf8'));
const cases = new Set(['library_changes_during_final_hash', 'verified_cache_binds_current_file',
  'library_directory_points_to_card_source', 'library_directory_link']);
const rows = [];
for (const row of records) {
  if (!cases.has(row.case)) continue;
  const progress = row.progress || row.first;
  rows.push({case: row.case, kind: row.kind, phase: row.phase || null,
    status: module.namespace.doneStatusText(progress),
    canEject: module.namespace.canEject(progress), summary: module.namespace.summarizeImport(progress)});
}
fs.writeFileSync(out + '/backend-text.json', JSON.stringify(rows, null, 2) + '\n');
console.log(JSON.stringify({checked: rows.length, ejectStatus: rows.filter((row) => row.canEject).length}));
