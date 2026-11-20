const test=require('node:test');
const assert=require('node:assert/strict');
const maps=require('../frontend-react/map-results.js');
function tree(value,lower=0,upper=10,population=3) {
    const category=value<lower?'LOW':value<upper?'INTERMEDIATE':'HIGH';
    return {id:1,source:'YOLO',sources:['YOLO'],confidence:0.8,
        healthStatus:{LOW:'SUSPECT',INTERMEDIATE:'STRESS',HIGH:'SAIN'}[category],
        exgMetadata:{value,category,lowerThreshold:lower,upperThreshold:upper,populationSize:population,
            classificationMethod:population>5?'PERCENTILES_15_30':'FIXED_SMALL_SAMPLE',
            formula:'2G-R-B',rgbScale:'UNNORMALIZED_0_255',nominalWindowSize:7,
            sampleWidth:7,sampleHeight:7,samplePixelCount:49}};
}
test('category labels follow existing strict comparisons, including zero and equal thresholds',()=>{
    for(const t of [tree(-2),tree(0),tree(10),tree(2,2,2,8),tree(1,2,2,8)])assert.equal(maps.exgInfo(t).verified,true);
    assert.match(maps.exgInfo(tree(-2)).label,/moins verte/);
    assert.match(maps.exgInfo(tree(0)).label,/intermédiaire/);
    assert.match(maps.exgInfo(tree(10)).label,/plus verte/);
    assert.match(maps.details(tree(0)),/Valeur ExG calculée : 0 /);
    assert.match(maps.details(tree(0)),/Seuils fixes/);
});
test('missing or invalid ExG never becomes an invented value or a verified category',()=>{
    for(const value of [null,undefined,NaN,Infinity,-Infinity,'0',{},511,-511]) {
        const t=tree(10);t.exgMetadata.value=value;
        assert.equal(maps.exgInfo(t).value,null);
        assert.equal(maps.exgInfo(t).verified,false);
        assert.match(maps.details(t),/non renseignée ou invalide/);
    }
    const missing=maps.exgInfo({healthStatus:'SAIN'});
    assert.equal(missing.value,null);assert.equal(missing.verified,false);
    for(const change of [{upperThreshold:-1},{category:'LOW'},{samplePixelCount:48},{classificationMethod:'UNKNOWN'},
        {populationSize:0},{sampleWidth:8},{formula:'NDVI'},{lowerThreshold:'0'}]) {
        const t=tree(10);Object.assign(t.exgMetadata,change);assert.equal(maps.exgInfo(t).verified,false);
    }
    assert.equal(maps.confidence({confidence:1.1}),null);
    assert.equal(maps.confidence({confidence:-1}),null);
    assert.equal(maps.confidence({confidence:0}),0);
});
test('details show provenance, detection score nature and methodology, without diagnostic labels',()=>{
    const t=tree(10);t.source='OPENCV';t.sources=['YOLO','OPENCV'];
    const html=maps.details(t);
    assert.match(html,/maximum des scores/);assert.match(html,/non calibré/);
    assert.match(html,/Position GPS estimée/);assert.match(html,/#exgMethodology/);
    assert.doesNotMatch(html,/Catégorie ExG : SAIN|Catégorie ExG : STRESS|Catégorie ExG : SUSPECT/);
});
