const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../dist/app.js'), 'utf8');
const functionSource = source.slice(source.indexOf('async function importVideo('), source.indexOf("$('uploadButton').onclick"));
const revoked = [];
const sandbox = {
  setTimeout, clearTimeout,
  URL: {createObjectURL: () => 'blob:rejected', revokeObjectURL: url => revoked.push(url)},
  document: {createElement: () => ({
    set src(value) { queueMicrotask(() => this.onerror()); },
    removeAttribute() {}, load() {}
  })}
};
vm.createContext(sandbox);
vm.runInContext(`
let jobId=null, recording=false;
let clipFile={name:'original.mp4'};
let state={annotations:[{text:'Keep this note'}]};
let cleared=false;
function toast() {}
function clearMedia() { cleared=true; }
`, sandbox);
vm.runInContext(functionSource, sandbox);
(async () => {
  await sandbox.importVideo({name:'broken.mp4',size:100});
  assert.equal(vm.runInContext('clipFile.name',sandbox),'original.mp4');
  assert.equal(vm.runInContext('state.annotations[0].text',sandbox),'Keep this note');
  assert.equal(vm.runInContext('cleared',sandbox),false);
  assert.deepEqual(revoked,['blob:rejected']);
  console.log('PASS: rejected video imports preserve the current clip and edits, and release the rejected object URL.');
})().catch(error => { console.error(error); process.exitCode=1; });
