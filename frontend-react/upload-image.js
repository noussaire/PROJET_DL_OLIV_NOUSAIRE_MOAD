(function(root) {
    'use strict';
    const MAX_FILE=8*1024*1024, MAX_BODY=12*1024*1024, MAX_PIXELS=12000000;
    const parameters={imgsz:1280,conf:0.20,iou:0.50,max_det:1000,device:'cpu'};
    function fit(width,height,imageWidth,imageHeight) {
        const scale=Math.min(width/imageWidth,height/imageHeight);
        return {scale,x:(width-imageWidth*scale)/2,y:(height-imageHeight*scale)/2,width:imageWidth*scale,height:imageHeight*scale};
    }
    function toPixel(x,y,frame,imageWidth,imageHeight) {
        if(!frame||frame.scale<=0||x<frame.x||y<frame.y||x>frame.x+frame.width||y>frame.y+frame.height)return null;
        return {x:Math.max(0,Math.min(imageWidth,(x-frame.x)/frame.scale)),y:Math.max(0,Math.min(imageHeight,(y-frame.y)/frame.scale))};
    }
    function validate(payload,request) {
        if(!payload||payload.success!==true)throw Error(payload?.error||'Analyse image échouée.');
        const finite=Number.isFinite;
        if(payload.mode!=='LIVE'||payload.engine!=='YOLO'||payload.model!=='YOLO11m V1'||payload.coordinateSystem!=='IMAGE_PIXELS'||
            payload.imageId!==request.imageId||payload.imageWidth!==request.imageWidth||payload.imageHeight!==request.imageHeight||
            !Number.isInteger(payload.imageWidth)||!Number.isInteger(payload.imageHeight)||payload.imageWidth<=0||payload.imageHeight<=0||
            payload.imageWidth*payload.imageHeight>MAX_PIXELS||!Array.isArray(payload.detections)||payload.totalDetections!==payload.detections.length||
            !Number.isInteger(payload.rawDetectionCount)||payload.rawDetectionCount<payload.totalDetections||
            !Number.isFinite(payload.inferenceTimeMs)||payload.inferenceTimeMs<0||!Number.isFinite(payload.totalTimeMs)||payload.totalTimeMs<0||
            !Array.isArray(payload.warnings)||payload.warnings.some(w=>typeof w!=='string')||
            Object.entries(parameters).some(([k,v])=>payload.inferenceParameters?.[k]!==v))throw Error('Réponse image incompatible ou provenance invalide.');
        const ids=new Set();
        for(const d of payload.detections) {
            if(!Number.isInteger(d.id)||ids.has(d.id)||d.source!=='YOLO'||d.classId!==0||d.className!=='trees'||
                !finite(d.confidence)||d.confidence<0||d.confidence>1||!Array.isArray(d.bboxPx)||d.bboxPx.length!==4||
                !d.bboxPx.every(finite)||!Array.isArray(d.centerPx)||d.centerPx.length!==2||!d.centerPx.every(finite))throw Error('Détection image invalide.');
            ids.add(d.id);
            const [x1,y1,x2,y2]=d.bboxPx,[cx,cy]=d.centerPx;
            if(!(0<=x1&&x1<x2&&x2<=payload.imageWidth&&0<=y1&&y1<y2&&y2<=payload.imageHeight&&
                Math.abs(cx-(x1+x2)/2)<1e-5&&Math.abs(cy-(y1+y2)/2)<1e-5))throw Error('Coordonnées pixels invalides.');
        }
        return payload;
    }
    async function post(fetchImpl,request,signal,url='http://localhost:8080/api/v1/images/analyser') {
        const body=JSON.stringify(request);
        if(new TextEncoder().encode(body).length>MAX_BODY)throw Error('Corps JSON supérieur à 12 MiB.');
        let response;
        try {response=await fetchImpl(url,{method:'POST',headers:{'Content-Type':'application/json'},body,signal});}
        catch(error){if(error.name==='AbortError')throw error;throw Error('Service image indisponible (:8080). Aucune simulation utilisée.');}
        let payload;try{payload=await response.json();}catch(_){throw Error('Réponse du service image illisible.');}
        if(!response.ok)throw Error(payload.error||'Analyse image refusée ('+response.status+').');
        return validate(payload,request);
    }
    function mount() {
        const el=id=>document.getElementById(id),canvas=el('imageRoiCanvas'),img=el('imageViewerImg');
        const scope=el('imageAnalysisScope'),view=el('imageDetectionView'),editButton=el('imageRoiEdit');
        let active=false,bitmap=null,encoded=null,imageId=null,fileName='',version=0,abort=null,result=null,roi=[],editing=false,selected=null,drag=-1,snapshot=null;
        const shared=['resTotalTrees','resSubtitle','resConfidence','resDiameter','resInferenceTime','resSains','resStress','resSuspects',
            'resJeunes','resAdultes','resCentenaires','resYoloRaw','resHybridCount','rawCountNote','treeDetailContainer','analysisStatus'];
        const live=()=>active&&!el('demoMode').checked;
        function layout() {
            el('detectionWorkspaceView').classList.toggle('image-live-workspace',live());
            el('mapResultsControls').classList.toggle('hidden',active);
            el('imageScopeNotice').classList.toggle('hidden',!live());
            el('analysisStatus').previousElementSibling.classList.toggle('hidden',live());
            el('resSains').parentElement.parentElement.classList.toggle('hidden',live());
            el('resJeunes').parentElement.classList.toggle('hidden',live());
            el('resJeunes').parentElement.nextElementSibling.classList.toggle('hidden',live());
            el('exgMethodology').classList.toggle('hidden',live());
            el('rawCountLabel').textContent=live()?'YOLO dans la zone image':'YOLO brut dans le polygone';
            const code=el('btnAnalyzeYolo').nextElementSibling.querySelector('code');
            if(code)code.textContent=live()?':8080/api/v1/images/analyser':':8080/api/v1/parcelles/analyser';
            el('mediaHelpText').classList.toggle('hidden',live());
            el('verticesGrid').parentElement.classList.toggle('hidden',live());
            el('viewerWrapper').nextElementSibling.classList.toggle('hidden',active);
        }
        function message(text){el('imageLiveMessage').textContent=text;}
        function clearResults() {
            version++;if(abort)abort.abort();abort=null;result=null;selected=null;
            if(live()) {
                for(const id of shared)if(el(id))el(id).textContent='—';
                el('resSubtitle').textContent='Image LIVE · aucun résultat disponible';
                el('resHybridCount').textContent='Non appliqué';
                el('rawCountNote').textContent='Image : YOLO uniquement. Aucun ExG, GPS, âge ou dimension en mètres.';
                el('treeDetailContainer').textContent='Sélectionner une détection après analyse.';
                el('btnAnalyzeYolo').disabled=false;
            }
        }
        function frame(){return bitmap?fit(canvas.clientWidth,canvas.clientHeight,bitmap.width,bitmap.height):null;}
        function draw() {
            if(!live())return;
            img.style.visibility='hidden';canvas.style.touchAction='none';
            const w=canvas.clientWidth,h=canvas.clientHeight,dpr=window.devicePixelRatio||1;
            canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
            const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
            if(!bitmap||!w||!h)return;
            const f=frame(),xy=p=>[f.x+p.x*f.scale,f.y+p.y*f.scale];
            ctx.fillStyle='#ffffff';ctx.fillRect(f.x,f.y,f.width,f.height);ctx.drawImage(bitmap,f.x,f.y,f.width,f.height);
            for(const d of result?.detections||[]) {
                const [x1,y1,x2,y2]=d.bboxPx,[cx,cy]=d.centerPx;
                ctx.strokeStyle=d.id===selected?'#ffffff':'#00e676';ctx.fillStyle='#00e676';ctx.lineWidth=d.id===selected?3:1.5;
                if(view.value!=='points')ctx.strokeRect(f.x+x1*f.scale,f.y+y1*f.scale,(x2-x1)*f.scale,(y2-y1)*f.scale);
                if(view.value!=='rectangles'){ctx.beginPath();ctx.arc(f.x+cx*f.scale,f.y+cy*f.scale,d.id===selected?5:3,0,2*Math.PI);ctx.fill();ctx.stroke();}
            }
            if(scope.value==='roi'&&roi.length) {
                ctx.strokeStyle='#ffb300';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(...xy(roi[0]));
                roi.slice(1).forEach(p=>ctx.lineTo(...xy(p)));if(roi.length>=3)ctx.closePath();ctx.stroke();
                if(editing)for(const p of roi){ctx.beginPath();ctx.arc(...xy(p),6,0,2*Math.PI);ctx.fillStyle='#ffffff';ctx.fill();ctx.stroke();}
            }
        }
        async function loadFile(file) {
            clearResults();const token=version;
            if(bitmap)bitmap.close?.();bitmap=null;encoded=null;imageId=null;roi=[];scope.value='whole';editing=false;
            draw();message('Chargement et vérification de l’image…');
            try {
                if(!file||file.size===0||file.size>MAX_FILE)throw Error('Choisir une image non vide de 8 MiB maximum.');
                if(!/\.(jpe?g|png|webp)$/i.test(file.name)|| (file.type&&!['image/jpeg','image/png','image/webp'].includes(file.type)))
                    throw Error('Formats autorisés : JPG, PNG et WebP.');
                const decoded=await createImageBitmap(file,{imageOrientation:'from-image'});
                if(token!==version){decoded.close();return;}
                if(decoded.width*decoded.height>MAX_PIXELS){decoded.close();throw Error('Limite : 12 millions de pixels décodés.');}
                const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onerror=()=>reject(Error('Lecture du fichier impossible.'));reader.onload=()=>resolve(reader.result);reader.readAsDataURL(file);});
                if(token!==version){decoded.close();return;}
                bitmap=decoded;encoded=String(data).split(',')[1];imageId=crypto.randomUUID();fileName=file.name;
                message(fileName+' · '+bitmap.width+' × '+bitmap.height+' px orientés · prêt pour une analyse réelle.');draw();
            } catch(error){if(token===version){message(error.message);draw();}}
        }
        function details(d) {
            selected=d.id;
            const target=el('treeDetailContainer');target.replaceChildren();
            for(const text of ['Arbre #'+d.id+' · classe '+d.className,'Source : YOLO · score de détection '+(d.confidence*100).toFixed(2)+' % (pas une probabilité de santé)',
                'Rectangle en pixels : '+d.bboxPx.map(x=>x.toFixed(2)).join(', '),'Centre en pixels : '+d.centerPx.map(x=>x.toFixed(2)).join(', '),
                'GPS, dimensions en mètres, âge et diagnostic sanitaire : non calculés.']) {
                const p=document.createElement('p');p.textContent=text;target.appendChild(p);
            }
            draw();
        }
        async function analyze() {
            if(!live())return;
            if(!bitmap||!encoded){message('Importer une image JPG, PNG ou WebP avant l’analyse LIVE.');return;}
            if(scope.value==='roi'&&roi.length<3){message('Tracer au moins trois sommets ou choisir l’image entière.');return;}
            clearResults();const token=version;
            abort=new AbortController();const controller=abort;
            let timedOut=false;
            const timer=setTimeout(()=>{timedOut=true;controller.abort();},65000);
            const request={imageBase64:encoded,imageId,imageWidth:bitmap.width,imageHeight:bitmap.height,
                roiPx:scope.value==='roi'?roi.map(p=>({...p})):null,mode:'LIVE'};
            el('btnAnalyzeYolo').disabled=true;message('Analyse LIVE CPU en cours…');
            try {
                const payload=await post((...args)=>fetch(...args),request,controller.signal);
                if(token!==version||!live())return;
                result=payload;editing=false;editButton.textContent='Modifier la ROI';
                el('resTotalTrees').textContent=payload.totalDetections+' arbres (YOLO)';
                el('resSubtitle').textContent='Image LIVE · coordonnées IMAGE_PIXELS · '+fileName;
                el('resYoloRaw').textContent=payload.totalDetections;el('resHybridCount').textContent='Non appliqué';
                el('resConfidence').textContent=payload.detections.length?(100*payload.detections.reduce((sum,d)=>sum+d.confidence,0)/payload.detections.length).toFixed(1)+' %':'—';
                el('resInferenceTime').textContent=payload.inferenceTimeMs+' ms YOLO · '+payload.totalTimeMs+' ms Python';
                el('analysisStatus').textContent='LIVE · '+payload.model+' · YOLO uniquement · '+payload.totalDetections+' détections';
                message(payload.warnings.join(' '));
                if(payload.detections.length)details(payload.detections[0]);else el('treeDetailContainer').textContent='Aucun arbre détecté. Aucun résultat simulé ajouté.';
                draw();
                document.dispatchEvent(new CustomEvent('olivesmart:image-result',{detail:{imageId:payload.imageId,totalDetections:payload.totalDetections}}));
            } catch(error) {
                if(token!==version||!live())return;
                result=null;message(timedOut?'Délai image dépassé. Le calcul CPU en cours peut continuer jusqu’à sa fin.':error.message);
                el('analysisStatus').textContent='Analyse image échouée · aucun résultat affiché';draw();
            } finally {clearTimeout(timer);if(token===version){abort=null;el('btnAnalyzeYolo').disabled=false;
                el('btnAnalyzeText').textContent='Analyser l’image avec YOLO11m V1';}}
        }
        function setActive(value) {
            if(value===active)return;
            if(value){snapshot=Object.fromEntries(shared.map(id=>[id,el(id)?.innerHTML]));active=true;if(live()){clearResults();message(bitmap?'Image prête pour analyse LIVE.':'Importer une image pour une analyse LIVE réelle.');}}
            else {version++;abort?.abort();abort=null;active=false;el('btnAnalyzeYolo').disabled=false;if(snapshot)for(const [id,html] of Object.entries(snapshot))if(el(id)&&html!==undefined)el(id).innerHTML=html;}
            el('imageLiveControls').classList.toggle('hidden',!live());
            layout();
            img.style.visibility=live()?'hidden':'';canvas.style.touchAction=live()?'none':'auto';
            el('imageDemoLegend').classList.toggle('hidden',live());el('imageRoiBanner').classList.toggle('hidden',live());
            if(live())draw();
        }
        function modeChanged() {
            clearResults();bitmap?.close?.();bitmap=null;encoded=null;roi=[];imageId=null;
            el('imageLiveControls').classList.toggle('hidden',!live());
            layout();
            img.style.visibility=live()?'hidden':'';canvas.style.touchAction=live()?'none':'auto';
            el('imageDemoLegend').classList.toggle('hidden',live());el('imageRoiBanner').classList.toggle('hidden',live());
            if(live()){message('Mode LIVE : réimporter une image. Aucun résultat DEMO utilisé.');draw();}
        }
        scope.addEventListener('change',()=>{clearResults();editing=scope.value==='roi';editButton.textContent=editing?'Terminer le tracé':'Modifier la ROI';draw();});
        editButton.addEventListener('click',()=>{if(!live())return;scope.value='roi';editing=!editing;clearResults();editButton.textContent=editing?'Terminer le tracé':'Modifier la ROI';draw();});
        view.addEventListener('change',draw);
        const pixel=event=>{const rect=canvas.getBoundingClientRect();return toPixel(event.clientX-rect.left,event.clientY-rect.top,frame(),bitmap.width,bitmap.height);};
        canvas.addEventListener('pointerdown',event=>{
            if(!live()||!bitmap)return;const p=pixel(event);if(!p)return;
            if(editing&&scope.value==='roi') {
                clearResults();drag=roi.findIndex(v=>Math.hypot(v.x-p.x,v.y-p.y)*frame().scale<14);
                if(drag<0){if(roi.length>=64)return;roi.push(p);drag=roi.length-1;}
                try{canvas.setPointerCapture(event.pointerId);}catch(_){}event.preventDefault();draw();
            } else {
                const f=frame();const matches=(result?.detections||[]).filter(d=>{
                    const [x1,y1,x2,y2]=d.bboxPx;
                    return (view.value!=='rectangles'&&Math.hypot(p.x-d.centerPx[0],p.y-d.centerPx[1])*f.scale<=9)||
                        (view.value!=='points'&&p.x>=x1&&p.x<=x2&&p.y>=y1&&p.y<=y2);
                }).sort((a,b)=>Math.hypot(p.x-a.centerPx[0],p.y-a.centerPx[1])-Math.hypot(p.x-b.centerPx[0],p.y-b.centerPx[1]));
                if(matches.length)details(matches[0]);
            }
        });
        canvas.addEventListener('pointermove',event=>{if(!live()||drag<0||!bitmap)return;const p=pixel(event);if(p){roi[drag]=p;draw();}});
        for(const type of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(type,()=>{drag=-1;});
        new ResizeObserver(()=>draw()).observe(el('imageUploadContainer'));
        return {loadFile,analyze,draw,setActive,modeChanged,clearROI(){clearResults();roi=[];draw();},
            async loadSample(){try{const response=await fetch('demo_drone_orthophoto.jpg');if(!response.ok)throw Error('Image exemple introuvable.');await loadFile(new File([await response.blob()],'exemple.jpg',{type:'image/jpeg'}));}catch(error){clearResults();message(error.message);}},
            getResult:()=>result};
    }
    const api={fit,toPixel,validate,post,mount,MAX_FILE,MAX_BODY,MAX_PIXELS};
    if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.OliveImageUpload=api;
})(typeof globalThis!=='undefined'?globalThis:this);
