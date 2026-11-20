const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
const root=path.resolve(__dirname,'..'),out=path.join(root,'resultats_tests','image-live');fs.mkdirSync(out,{recursive:true});
const reports=[];
const pending=[];
const server=http.createServer((req,res)=>{
 if(req.url==='/__await_upload'){pending.push(res);const timer=setTimeout(()=>res.end(),70000);res.on('close',()=>clearTimeout(timer));return;}
 if(req.url==='/__upload_config'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify({javaUrl:process.env.OLIVESMART_IMAGE_TEST_JAVA,exif:process.env.OLIVESMART_IMAGE_TEST_EXIF}));return;}
 if(req.url==='/__upload_report'&&req.method==='POST'){let body='';req.on('data',chunk=>body+=chunk);req.on('end',()=>{reports.push(JSON.parse(body));fs.writeFileSync(path.join(out,'browser-checks.json'),JSON.stringify(reports,null,2));res.end('ok');for(const waiting of pending.splice(0))waiting.end();});return;}
 const file=path.resolve(root,'.'+decodeURIComponent(req.url.split('?')[0]));if(!file.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}
 const type={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.jpg':'image/jpeg','.png':'image/png'}[path.extname(file)]||'application/octet-stream';
 fs.readFile(file,(error,data)=>{res.writeHead(error?404:200,{'Content-Type':type});res.end(error?'Not found':data);});
});
server.listen(0,'127.0.0.1',()=>{
 const inspector=path.join(process.env.USERPROFILE,'.codex/skills/design-taste-frontend/scripts/inspect.mjs');
 const url=`http://127.0.0.1:${server.address().port}/tests/upload-image-browser.html`;console.log(url);
 const child=spawn(process.execPath,[inspector,url,'--app','--widths','1440,768,390','--out',out],{stdio:'inherit'});
 const watchdog=setTimeout(()=>child.kill(),150000);
 child.on('error',error=>{console.error(error);clearTimeout(watchdog);server.close();process.exitCode=1;});
 child.on('exit',()=>{clearTimeout(watchdog);server.close();console.log('IMAGE BROWSER CHECKS',JSON.stringify(reports.map(r=>({ok:r.ok,width:r.width,error:r.error,count:r.frontendCount,checks:r.checks}))));
  if(![1440,768,390].every(width=>reports.some(r=>r.ok&&r.width===width))||reports.some(r=>!r.ok))process.exitCode=1;});
});
