// 直接执行原始 ES 模块，只在 API、状态和 DOM 边界提供合成对象。
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const repo = '/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio';
const out = '/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_a1a_r2';

const complete = (id) => ({card_id: id, state: 'done', done_shots: 1, total_shots: 1,
  imported_shots: 0, unreadable: [], verify_failed: [], scan_errors: [],
  coverage: {complete: true, dcim: 'present', all_imported: true, uncovered: [], not_importable: []}});

function node(tag, props, ...children) {
  return {tag, props, children: children.flat().filter((x) => x != null), textContent: '',
    append(...items) {this.children.push(...items);},
    replaceChildren(...items) {this.children = items; this.textContent = '';}};
}
function text(item) {
  if (item == null) return '';
  if (typeof item === 'string') return item;
  return item.textContent + (item.children || []).map(text).join(' ');
}

async function scenario(name) {
  const a = {id: 'CARD-A', label: 'A'};
  const b = {id: 'CARD-B', label: 'B'};
  const state = {card: null, cards: [], job: null, cardSummary: null, dismissedJobId: null};
  const elements = {banner: node('div', {}), 'card-status': node('div', {})};
  const posts = [];
  const calls = [];
  const errors = [];
  let visible = [a];
  const api = async (path, opts = {}) => {
    calls.push({path, method: opts.method || 'GET'});
    if (path === '/api/cards') return visible;
    if (path === '/api/cards/status') return {access_denied: false};
    if (path.endsWith('/summary')) return {shots: 3, new_shots: 3, verified: false};
    if (path === '/api/import') {
      posts.push(opts.body.card_id);
      if (name === 'request_error' && posts.length === 1) {
        const error = new Error('local request failed');
        error.code = 'offline';
        throw error;
      }
      return {id: 'JOB-' + opts.body.card_id, kind: 'import', running: true,
        progress: {...complete(opts.body.card_id), state: 'running'}};
    }
    if (path.startsWith('/api/jobs/')) {
      const id = path.slice('/api/jobs/JOB-'.length);
      return {id: 'JOB-' + id, kind: 'import', running: false,
        progress: complete(name === 'missing_source' ? null : id)};
    }
    throw new Error(path);
  };
  const context = vm.createContext({document: {getElementById: (id) => elements[id]}});
  const summary = new vm.SourceTextModule(fs.readFileSync(repo + '/web/assets/import_summary.js', 'utf8'), {context});
  const boundary = (values) => new vm.SyntheticModule(Object.keys(values), function () {
    for (const [key, value] of Object.entries(values)) this.setExport(key, value);
  }, {context});
  const modules = {
    './api.js': boundary({api}), './state.js': boundary({state, emit() {}}),
    './dom.js': boundary({h: node, toast() {}, toastError(error) {errors.push(error.code);}}),
    './import_summary.js': summary,
  };
  const module = new vm.SourceTextModule(fs.readFileSync(repo + '/web/assets/import.js', 'utf8'), {context});
  await module.link((specifier) => modules[specifier]);
  await module.evaluate();
  const app = module.namespace;
  await app.refreshCards();
  await Promise.resolve();
  await Promise.resolve();
  if (name === 'request_error') {
    await app.refreshCards();
    await Promise.resolve();
    return {name, posts, calls, errors, banner: text(elements.banner),
      status: elements['card-status'].textContent,
      retryAvailable: posts.length > 1 || text(elements.banner).includes('导入')};
  }
  assert.deepEqual(posts, [a.id]);
  if (name === 'same_session') {
    await app.tickImport();
    assert.equal(elements['card-status'].textContent, '存储卡：可以推出');
    assert.deepEqual(posts, [a.id]);
  } else {
    visible = [b];
    await app.refreshCards();
    assert.deepEqual(posts, [a.id]);
    if (name === 'removed_before_done') {
      visible = [];
      await app.refreshCards();
    }
    await app.tickImport();
    await Promise.resolve();
    await Promise.resolve();
    if (name === 'removed_before_done') {
      assert.deepEqual(posts, [a.id]);
      assert.equal(elements['card-status'].textContent, '存储卡：未插入');
    } else {
      assert.deepEqual(posts, [a.id, b.id]);
      assert.equal(state.job.progress.card_id, b.id);
      assert(!text(elements.banner).includes('这张存储卡上的照片都已导入'));
      assert(!elements['card-status'].textContent.includes('可以推出'));
    }
  }
  return {name, posts, calls, stateCard: state.card && state.card.id,
    jobCard: state.job && state.job.progress.card_id, banner: text(elements.banner),
    status: elements['card-status'].textContent};
}

const results = [];
for (const name of ['same_session', 'changed_session', 'removed_before_done', 'missing_source']) {
  results.push(await scenario(name));
}
const retry = await scenario('request_error');
results.push(retry);
fs.writeFileSync(out + '/frontend.json', JSON.stringify(results, null, 2) + '\n');
console.log(JSON.stringify({coreCases: 4, corePassed: true, requestRetryPassed: retry.retryAvailable}));
process.exitCode = retry.retryAvailable ? 0 : 1;
