const test=require('node:test'),assert=require('node:assert/strict');
const upload=require('../frontend-react/upload-image.js');
const request={imageId:'a',imageWidth:120,imageHeight:80,mode:'LIVE',imageBase64:'YWJj'};
const payload=()=>({success:true,mode:'LIVE',engine:'YOLO',model:'YOLO11m V1',coordinateSystem:'IMAGE_PIXELS',
    imageId:'a',imageWidth:120,imageHeight:80,totalDetections:1,rawDetectionCount:1,
    inferenceParameters:{imgsz:1280,conf:.2,iou:.5,max_det:1000,device:'cpu'},inferenceTimeMs:1,totalTimeMs:2,warnings:[],
    detections:[{id:1,bboxPx:[10,10,30,30],centerPx:[20,20],confidence:.8,classId:0,className:'trees',source:'YOLO'}]});
test('object-contain transforms correctly reject margins and preserve pixels at different sizes',()=>{
    for(const [w,h] of [[500,500],[900,400],[320,600]]){
        const frame=upload.fit(w,h,120,80);
        const point=upload.toPixel(frame.x+20*frame.scale,frame.y+20*frame.scale,frame,120,80);
        assert.ok(Math.abs(point.x-20)<1e-9&&Math.abs(point.y-20)<1e-9);
        assert.equal(upload.toPixel(frame.x-1,frame.y,frame,120,80),null);
    }
});
test('LIVE contract accepts real pixel boxes and empty results; rejects simulation or stale image',()=>{
    assert.equal(upload.validate(payload(),request).totalDetections,1);
    assert.equal(upload.validate({...payload(),totalDetections:0,rawDetectionCount:0,detections:[]},request).totalDetections,0);
    for(const change of [{mode:'DEMO'},{engine:'OPENCV'},{imageId:'old'},{coordinateSystem:'GPS'},
        {totalDetections:2},{detections:[{...payload().detections[0],source:'DEMO'}]},
        {detections:[{...payload().detections[0],bboxPx:[10,10,130,30]}]}])assert.throws(()=>upload.validate({...payload(),...change},request));
});
test('server/network/invalid response failures never become simulated results',async()=>{
    await assert.rejects(upload.post(async()=>{throw Error('offline');},request),/indisponible/);
    await assert.rejects(upload.post(async()=>({ok:false,status:504,json:async()=>({error:'Delai depasse'})}),request),/Delai/);
    await assert.rejects(upload.post(async()=>({ok:true,json:async()=>({...payload(),mode:'DEMO'})}),request),/provenance/);
    assert.equal((await upload.post(async()=>({ok:true,json:async()=>payload()}),request)).totalDetections,1);
});
