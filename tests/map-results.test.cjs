const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const maps = require('../frontend-react/map-results.js');
function fixture() {
    const group = { layers: [], clearLayers() { this.layers = []; } };
    const clicks = [];
    function layer(kind, coordinates, options) {
        return { kind, coordinates, options: {...options}, events: {},
            addTo(g) { g.layers.push(this); return this; },
            setStyle(style) { Object.assign(this.options, style); return this; },
            setRadius(radius) { this.options.radius = radius; return this; },
            bringToFront() { return this; },
            bindTooltip(html) { this.tooltip = html; return this; },
            on(event, callback) { this.events[event] = callback; return this; }
        };
    }
    let rendererCount = 0;
    const L = { canvas(options) { rendererCount++; return {options}; },
        circleMarker: (xy, opts) => layer('point', xy, opts),
        rectangle: (xy, opts) => layer('rect', xy, opts) };
    return { group, clicks, controller: maps.createController(L, group, id => clicks.push(id)), rendererCount: () => rendererCount };
}
function tree(id = 1) { return { id, lat:31.6338, lng:-7.9653, lat_min:31.63377,
    lat_max:31.63383, lng_min:-7.96534, lng_max:-7.96526,
    health:'SAIN', source:'YOLO', sources:['YOLO'], confidence:0.8, crownDiameterMeters:6 }; }
test('three modes preserve coordinates and tree data; default is points only', () => {
    const f = fixture(), t = tree(), before = JSON.stringify(t);
    f.controller.render([t]);
    assert.equal(f.controller.getMode(), 'points');
    assert.deepEqual(f.group.layers.map(x => x.kind), ['point']);
    assert.deepEqual(f.group.layers[0].coordinates, [t.lat, t.lng]);
    f.controller.setMode('rectangles');
    assert.deepEqual(f.group.layers.map(x => x.kind), ['rect']);
    assert.deepEqual(f.group.layers[0].coordinates, [[t.lat_min,t.lng_min],[t.lat_max,t.lng_max]]);
    f.controller.setMode('both');
    assert.deepEqual(f.group.layers.map(x => x.kind), ['rect','point']);
    assert.equal(JSON.stringify(t), before);
    assert.equal(f.rendererCount(), 1);
});
test('points and rectangles both support selection; no polygon click bubbling', () => {
    const f=fixture(); f.controller.render([tree()]); f.controller.setMode('both');
    for(const layer of f.group.layers) { layer.events.click(); assert.equal(layer.options.bubblingMouseEvents, false); }
    assert.deepEqual(f.clicks,[1,1]);
    f.controller.select(1);
    assert.equal(f.controller.entries.get(1).point.options.radius,5.5);
    f.controller.setMode('points');
    assert.equal(f.controller.entries.get(1).point.options.radius,5.5);
});
test('raw 179 and hybrid 219 remain distinct in every mode; no raw points invented', () => {
    const trees=Array.from({length:219},(_,i)=>tree(i+1)), f=fixture();
    const summary=maps.counts({totalTrees:219,trees,mode:'LIVE',analysisMetadata:{yoloInPolygonCount:179,hybridCount:219}});
    assert.deepEqual(summary,{raw:179,hybrid:219,demo:false,coherent:true});
    f.controller.render(trees);
    for(const mode of ['points','rectangles','both']) {
        f.controller.setMode(mode);
        assert.equal(f.controller.entries.size,219);
        assert.equal(f.group.layers.length,mode==='both'?438:219);
    }
    assert.equal(maps.counts({totalTrees:219,trees}).raw,null);
    assert.equal(maps.counts({totalTrees:219,trees,analysisMetadata:{hybridCount:218}}).coherent,false);
    assert.equal(maps.counts({totalTrees:0,trees:[],analysisMetadata:{yoloInPolygonCount:0}}).raw,0);
});
test('no fabricated confidence/dimensions/age; zero confidence is retained; HTML is escaped', () => {
    const html=maps.details({id:'<img onerror=x>',lat:0,lng:0,confidence:0,age:'140 ans (Centenaire)',health:'SUSPECT',source:'OPENCV'});
    assert.match(html,/0 %/); assert.match(html,/non calibré/);
    assert.match(html,/Dimensions de couronne non renseignées/);
    assert.match(html,/Âge non déterminé/); assert.doesNotMatch(html,/Centenaire|140 ans|4\.2|90 %/);
    assert.match(html,/&lt;img/); assert.doesNotMatch(html,/<img/);
    assert.equal(maps.bounds({lat:0,lng:0}),null);
});
test('500 trees use one renderer and exactly one point each, with no coordinate mutation', () => {
    const trees=Array.from({length:500},(_,i)=>({...tree(i),lat:31.63+i/100000}));
    const snapshot=JSON.stringify(trees), f=fixture(); f.controller.render(trees);
    assert.equal(f.group.layers.length,500); assert.equal(f.rendererCount(),1);
    assert.ok(f.group.layers.every(x=>x.options.radius===3.5));
    assert.equal(JSON.stringify(trees),snapshot);
    f.controller.render([]); assert.equal(f.group.layers.length,0);
});
test('both frontend copies and new script are identical', () => {
    for(const name of ['index.html','map-results.js']) assert.equal(fs.readFileSync('frontend-react/'+name,'utf8'),
        fs.readFileSync('springboot-microservice-olive/src/main/resources/static/'+name,'utf8'));
});
