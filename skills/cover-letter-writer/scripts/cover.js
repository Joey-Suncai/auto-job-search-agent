// usage: node cover.js "<Company — Role>" ["<date>"]   (body: $COVER_TXT or <data home>/data/work/cover/cover.txt, output next to it; name / contact from config/profile.json, JSA-077)
const fs=require('fs'),path=require('path');const {Document,Packer,Paragraph,TextRun}=require('docx');
const P=require(path.join(__dirname,'..','..','..','config','profile.js')),K=P.contact||{};
const W=require(path.join(__dirname,'..','..','..','config','paths.js')).work('cover');   // input + output in the data home, not the read-only code (JSA-377)
fs.mkdirSync(W,{recursive:true});
const HEAD=process.argv[2]||'Company — Role',DATE=process.argv[3]||new Date().toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'});
const CO=HEAD.split(' — ')[0].replace(/[^A-Za-z0-9]+/g,'_');
const t=fs.readFileSync(process.env.COVER_TXT||W+'/cover.txt','utf8').trim().split('\n\n');
const F='Calibri',run=(s,o={})=>new TextRun({text:s,font:F,size:o.size||22,bold:o.bold,color:o.color});
const kids=[new Paragraph({spacing:{after:0},children:[run(P.name.full,{size:36,bold:true,color:'800000'})]}),
 new Paragraph({spacing:{after:240},children:[run([K.city_state,K.phone,K.email,K.linkedin,K.website].filter(Boolean).join('  |  '),{size:19,color:'555555'})]}),
 new Paragraph({spacing:{after:200},children:[run(DATE)]}),
 new Paragraph({spacing:{after:200},children:[run(HEAD,{bold:true})]})];
t.slice(0,-1).forEach(p=>kids.push(new Paragraph({spacing:{after:180,line:276},children:p.split('\n').flatMap((l,i)=>i?[new TextRun({break:1}),run(l)]:[run(l)])})));
kids.push(new Paragraph({children:[run('Sincerely,')]}),new Paragraph({children:[run(P.name.signature||P.name.full)]}));
const doc=new Document({sections:[{properties:{page:{margin:{top:1080,bottom:1080,left:1080,right:1080}}},children:kids}]});
Packer.toBuffer(doc).then(b=>fs.writeFileSync(W+'/'+P.name.file_prefix+'_Cover_Letter_'+CO+'.docx',b));
