// 执行产品原始模块，用本轮真实后端结果核对文字、重试按钮和请求次数。
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const out = '/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_a1a_r3';
const repo = '/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio';
const records = fs.readFileSync(out + '/observations.jsonl', 'utf8').trim().split('\n').map(JSON.parse);

function node(tag, props = {}, ...children) {
  return {tag, props, children: children.flat().filter((item) => item != null), textContent: '',
    append(...items) {this.children.push(...items);},
    replaceChildren(...items) {this.children = items; this.textContent = '';}};
}
function text(item) {
  if (item == null) return '';
  if (typeof item === 'string') return item;
  return item.textContent + (item.children || []).map(text).join(' ');
}
function buttons(item) {
  if (item == null || typeof item === 'string') return [];
  return [...(item.tag === 'button' ? [item] : []), ...(item.children || []).flatMap(buttons)];
}
async function settle() {
  for (let index = 0; index < 12; index++) await Promise.resolve();
}

async function scenario(name, progress, requestError = false) {
  const card = {id: 'LOCAL-CARD', label: 'CARD'};
  const state = {card: null, cards: [], job: null, cardSummary: null, dismissedJobId: null};
  const elements = {banner: node('div'), 'card-status': node('div')};
  const posts = [];
  const errors = [];
  const api = async (path, opts = {}) => {
    if (path === '/api/cards') return [card];
    if (path === '/api/cards/status') return {access_denied: false};
    if (path.endsWith('/summary')) return {shots: 1, new_shots: 1, verified: false};
    if (path === '/api/import') {
      posts.push(opts.body.card_id);
      if (requestError && posts.length === 1) {
        const error = new Error('local request did not complete');
        error.code = 'offline';
        throw error;
      }
      return {id: 'LOCAL-JOB', kind: 'import', running: true,
        progress: {...progress, card_id: card.id, state: 'running'}};
    }
    if (path.startsWith('/api/jobs/')) return {id: 'LOCAL-JOB', kind: 'import', running: false,
      progress: {...progress, card_id: card.id}};
    throw new Error(path);
  };
  const context = vm.createContext({document: {getElementById: (id) => elements[id]}});
  const summary = new vm.SourceTextModule(fs.readFileSync(repo + '/web/assets/import_summary.js', 'utf8'), {context});
  const boundary = (values) => new vm.SyntheticModule(Object.keys(values), function () {
    for (const [key, value] of Object.entries(values)) this.setExport(key, value);
  }, {context});
  const modules = {'./api.js': boundary({api}), './state.js': boundary({state, emit() {}}),
    './dom.js': boundary({h: node, toast() {}, toastError(error) {errors.push(error.code);}}), './import_summary.js': summary};
  const module = new vm.SourceTextModule(fs.readFileSync(repo + '/web/assets/import.js', 'utf8'), {context});
  await module.link((specifier) => modules[specifier]);
  await module.evaluate();
  const app = module.namespace;
  await app.refreshCards();
  await settle();
  if (requestError) {
    for (let index = 0; index < 5; index++) await app.refreshCards();
    assert.equal(posts.length, 1);
    const retry = buttons(elements.banner).find((button) => text(button) === '导入');
    assert(retry && typeof retry.props.onclick === 'function');
    assert(!elements['card-status'].textContent.includes('可以推出'));
    await retry.props.onclick();
    await settle();
    assert.equal(posts.length, 2);
  }
  await app.tickImport();
  await settle();
  const banner = text(elements.banner);
  const status = elements['card-status'].textContent;
  const canEject = summary.namespace.canEject(state.job.progress);
  for (let index = 0; index < 5; index++) {
    await app.refreshCards();
    await app.tickImport();
  }
  assert.equal(posts.length, requestError ? 2 : 1);
  const result = {name, posts: [...posts], errors, banner, status, canEject,
    buttons: buttons(elements.banner).map(text), automatic_repeated_posts: 0};
  if (!requestError) {
    assert.equal(canEject, false);
    assert.equal(status, '存储卡：有未导入的照片');
    assert(banner.includes('未能导入') && !banner.includes('都已导入'));
    const retry = buttons(elements.banner).find((button) => text(button) === '导入');
    assert(retry && typeof retry.props.onclick === 'function');
    await retry.props.onclick();
    await settle();
    assert.equal(posts.length, 2);
    await app.tickImport();
    await settle();
    assert.equal(summary.namespace.canEject(state.job.progress), false);
    result.explicit_retry_posts = posts.length;
  } else {
    assert.equal(canEject, true);
    assert.equal(status, '存储卡：可以推出');
  }
  return result;
}

const results = [];
const selected = new Map();
for (const row of records) {
  if (row.case === 'refusal_with_empty_index' || row.case === 'unstable_content_result') {
    selected.set(`${row.case}-${row.kind}-${row.links || ''}`, row);
  }
}
for (const row of selected.values()) {
  if (row.case === 'refusal_with_empty_index') {
    results.push(await scenario(`${row.case}-${row.kind}-${row.links}`, row.first));
  }
  if (row.case === 'unstable_content_result') {
    results.push(await scenario(`${row.case}-${row.kind}`, row.progress));
  }
}
assert.equal(results.length, 6);
const clean = {state: 'done', imported_shots: 1, unreadable: [], verify_failed: [], scan_errors: [], write_refused: [],
  coverage: {complete: true, dcim: 'present', uncovered: [], not_importable: [], all_imported: true}};
results.push(await scenario('first_request_error_manual_retry', clean, true));
fs.writeFileSync(out + '/ui-results.json', JSON.stringify(results, null, 2) + '\n');
console.log(JSON.stringify({scenarios: results.length, refused_or_unknown_no_eject: results.filter((row) => !row.canEject).length,
  first_request_manual_retry: true, automatic_repeated_posts: 0}));
