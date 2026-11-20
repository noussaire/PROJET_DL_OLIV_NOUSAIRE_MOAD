const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const trace = require('../frontend-react/traceability.js');
const tree = source => ({source, sources: [source], confidence: 0.88});
const payload = trees => ({success: true, mode: 'LIVE', engine: 'YOLO+OPENCV', model: 'best.pt (YOLOv8n)', trees, totalTrees: trees.length});

test('zero trees accepted, only one request, no Python retry', async () => {
    let calls = 0;
    const result = await trace.analyze(async () => {calls++; return {ok: true, json: async () => payload([])};}, []);
    assert.equal(result.totalTrees, 0);
    assert.equal(calls, 1);
});
test('Python failure returned through Java never becomes simulated trees', async () => {
    await assert.rejects(trace.analyze(async () => ({ok: false, json: async () => ({success:false, error:'Python unavailable', trees:[]})}), []), /Python unavailable/);
});
test('network failure stays an error', async () => {
    await assert.rejects(trace.analyze(async () => {throw Error('offline');}, []), /Spring Boot indisponible/);
});
test('YOLO and OPENCV sources preserved, even with identical confidence', () => {
    const p = payload([tree('YOLO'), tree('OPENCV')]);
    assert.equal(trace.validate(p), p);
    assert.deepEqual(p.trees.map(t => t.source), ['YOLO','OPENCV']);
});
test('DEMO allowed only when explicitly requested', () => {
    const p = {...payload([tree('DEMO')]), mode:'DEMO', engine:'DEMO'};
    assert.throws(() => trace.validate(p), /Provenance invalide/);
    assert.equal(trace.validate(p, 'DEMO'), p);
    assert.throws(() => trace.requireDemo(false), /simulation/);
    trace.requireDemo(true);
});
test('legacy and hidden mixed DEMO payloads rejected', () => {
    assert.throws(() => trace.validate({trees:[],totalTrees:0}), /Analyse échouée/);
    assert.throws(() => trace.validate(payload([{source:'YOLO',sources:['YOLO','DEMO']}])));
});
test('both HTML copies parse and agree; no browser or CDN required', () => {
    const html = fs.readFileSync('frontend-react/index.html','utf8');
    assert.equal(html, fs.readFileSync('springboot-microservice-olive/src/main/resources/static/index.html','utf8'));
    for (const [,code] of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)) new vm.Script(code);
});

function pageHarness(analyze) {
    const html = fs.readFileSync('frontend-react/index.html','utf8');
    const start = html.indexOf('        async function runYoloAnalysis()');
    const end = html.indexOf('        function isPointInRelativePolygon', start);
    const elements = new Map();
    const element = id => {
        if (!elements.has(id)) elements.set(id, {checked:false, disabled:false, innerText:'', textContent:'', innerHTML:'', classList:{remove(){}}});
        return elements.get(id);
    };
    const state = {currentActiveTab:'MAP_SAT', currentVertices:[{lat:1,lng:1},{lat:1,lng:2},{lat:2,lng:1}],
        analysisRequestId:0, activeTreesList:[tree('YOLO')], ALL_TREES_DATABASE:[tree('DEMO')],
        document:{getElementById:element}, performance:{now:()=>10}, map:null, fetch:()=>{},
        OliveTrace:{analyze}, renderSvgBoxes(){}, renderLeafletBoxes(){}, updateStatisticsDisplay(){}, selectTreeById(){},
        clearAnalysisResults(){state.activeTreesList=[];state.ALL_TREES_DATABASE=[];state.analysisRequestId++;}
    };
    vm.createContext(state);
    vm.runInContext(html.slice(start,end), state);
    return {state, element};
}
test('actual button handler preserves provenance in displayed trees', async () => {
    const {state} = pageHarness(async () => payload([tree('YOLO'),tree('OPENCV')]));
    await state.runYoloAnalysis();
    assert.deepEqual(Array.from(state.activeTreesList, t=>t.source), ['YOLO','OPENCV']);
});
test('actual button accepts zero and clears previously displayed trees', async () => {
    const {state,element} = pageHarness(async () => payload([]));
    await state.runYoloAnalysis();
    assert.equal(state.activeTreesList.length,0);
    assert.equal(state.ALL_TREES_DATABASE.length,0);
    assert.equal(element('btnAnalyzeYolo').disabled,false);
});
test('actual button displays errors without old or simulated trees', async () => {
    const {state,element} = pageHarness(async () => {throw Error('Python unavailable');});
    await state.runYoloAnalysis();
    assert.equal(state.activeTreesList.length,0);
    assert.equal(state.ALL_TREES_DATABASE.length,0);
    assert.equal(element('analysisStatus').textContent,'Python unavailable');
    assert.equal(element('btnAnalyzeYolo').disabled,false);
});
test('late DEMO response cannot overwrite a mode change', async () => {
    let complete;
    const {state,element} = pageHarness(() => new Promise(resolve=>{complete=resolve;}));
    element('demoMode').checked=true;
    const pending=state.runYoloAnalysis();
    state.clearAnalysisResults();
    element('demoMode').checked=false;
    complete({...payload([tree('DEMO')]),mode:'DEMO',engine:'DEMO'});
    await pending;
    assert.equal(state.activeTreesList.length,0);
});
