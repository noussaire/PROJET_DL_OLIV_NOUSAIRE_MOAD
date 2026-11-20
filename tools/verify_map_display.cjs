// Serve the existing UI and run the installed design skill's browser inspector.
// No model, production server, dependency installation, or API changes.
const http=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
const {spawn}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const out=path.join(root,'resultats_tests',process.env.OLIVESMART_UI_TEST_OUTPUT || 'map-display');
fs.mkdirSync(out,{recursive:true});
const reports=[];
const server=http.createServer((req,res)=>{
    if(req.method==='POST'&&req.url==='/__map_report') {
        let body=''; req.on('data',chunk=>body+=chunk); req.on('end',()=>{
            reports.push(JSON.parse(body)); res.writeHead(200);res.end('ok');
            fs.writeFileSync(path.join(out,'browser-checks.json'),JSON.stringify(reports,null,2));
        }); return;
    }
    const file=path.resolve(root,'.'+decodeURIComponent(req.url.split('?')[0]));
    if(!file.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}
    const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.json':'application/json','.jpg':'image/jpeg','.png':'image/png'};
    fs.readFile(file,(err,data)=>{
        res.writeHead(err?404:200,{'Content-Type':types[path.extname(file)]||'application/octet-stream'});
        res.end(err?'Not found':data);
    });
});
server.listen(0,'127.0.0.1',()=>{
    const inspector=path.join(process.env.USERPROFILE,'.codex','skills','design-taste-frontend','scripts','inspect.mjs');
    const url=`http://127.0.0.1:${server.address().port}/tests/map-display-browser.html`;
    console.log('Browser test fixture:',url);
    const child=spawn(process.execPath,[inspector,url,'--app','--widths','1440,768,390','--out',out],{stdio:'inherit'});
    const watchdog=setTimeout(()=>child.kill(),150000);
    child.on('error',error=>{console.error(error);server.close();clearTimeout(watchdog);process.exitCode=1;});
    child.on('exit',()=>{
        clearTimeout(watchdog); server.close();
        console.log('MAP BROWSER CHECKS',JSON.stringify(reports));
        if(![1440,768,390].every(width=>reports.some(r=>r.ok&&r.width===width))||reports.some(r=>!r.ok))process.exitCode=1;
    });
});
