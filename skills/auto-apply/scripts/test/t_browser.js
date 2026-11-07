const { chromium } = require('playwright'); const fs=require('fs');
(async()=>{const b=await chromium.launch();const p=await b.newPage();await p.goto('file://'+__dirname+'/form.html');
await p.evaluate(fs.readFileSync(__dirname+'/../form_helpers.js','utf8'));
await p.evaluate('globalThis.__cxProfile='+JSON.stringify(require('../../../../config/profile.js')));
await p.evaluate(fs.readFileSync(__dirname+'/../answer_rules.js','utf8'));
await p.evaluate('__cx.extract()');
const r=await p.evaluate('__cx.auto()'); console.log(r);
const f=JSON.parse(r).fill; console.log(await p.evaluate(`__cx.fill(${JSON.stringify(f)})`)); console.log(await p.evaluate('__cx.dump()'));await b.close();})();
