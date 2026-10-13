"""
Builds beef.html, the customer-facing Beef Cuts page. Uses the same catalogue rows as
index.html, so the chart and the comparator only ever show what the shop carries.
"""
import json
from build import public_rows, esc, shell, logo_and_ld, slug, PRIMALS, PRIMAL_OF

# ---------- "What are you cooking?" ----------
# (title, one-line why, [cut names]). Cuts that aren't in the catalogue are skipped.
SCENARIOS = [
 ("Grilling steaks tonight", "Hot and fast, medium rare, rest before you cut.",
  [("Ribeye steak","Richest, most forgiving."),("Strip sirloin","Beefy with a satisfying chew."),("NY sirloin","The everyday steak."),("Flat iron steak","Best value in the case.")]),
 ("Pot roast", "Low and slow until a fork twists in with no resistance.",
  [("Chuck roast","Every time. Falls apart."),("Rump roast","If you'd rather slice than shred."),("Bottom round roast","Leaner; slices neatly.")]),
 ("Roast beef for sandwiches", "Cook it rare and slice it paper thin.",
  [("Top round roast","What the deli uses."),("Eye round roast","Cheapest, keep it rare."),("Tenderloin roast","The luxury version.")]),
 ("A holiday centerpiece", "Salt it a day or two ahead, low oven, thermometer, big rest.",
  [("Bone-in rib roast","Prime rib on its bones."),("Boneless rib roast","Easier to carve."),("Tenderloin roast","Faster, leaner, elegant."),("Picanha roast","Different and impressive.")]),
 ("Fajitas, tacos, stir fry", "Marinate, cook fast, slice thin across the grain.",
  [("Skirt steak","The fajita steak."),("Flank steak","Leaner, tighter grain."),("Top round steak","Budget London broil."),("Shaved ribeye","Cheesesteaks and bulgogi.")]),
 ("The smoker", "Salt and pepper, 225 to 250, patience.",
  [("Brisket","The main event."),("Short ribs, bone-in","Dinosaur ribs."),("Tri-tip","Santa Maria style, done in an hour.")]),
 ("Burgers", "Handle it as little as possible and cook to 160.",
  [("Ground chuck 85%","Juicy. The burger grind."),("Ground round 90%","Leaner, for tacos and sauces.")]),
 ("Stew, chili, soup", "Cubes with fat and collagen turn silky; lean cubes turn dry.",
  [("Chuck roast","Cube it yourself for the best stew."),("Stew beef","Already cut."),("Oxtail","The richest broth there is."),("Beef bones","Stock and bone broth.")]),
 ("Feeding a crowd on a budget", "Roasts that cook like steaks, or steaks that eat above their price.",
  [("Chuck roast","Feeds a table for very little."),("Tri-tip","One roast, four to six people."),("Picanha roast","Skewer it Brazilian style."),("Flat iron steak","Tender for the money.")]),
 ("Something special for two", "One big steak to share.",
  [("Porterhouse","Strip and filet on one bone."),("Cowboy steak","Thick bone-in ribeye."),("Tenderloin steak","The tender one."),("Hanger steak","The butcher's own pick.")]),
 ("Kebabs and skewers", "Cubes that stay juicy over a hot fire.",
  [("NY sirloin","Classic kebab meat."),("Tenderloin tail","Filet texture, much less money."),("Picanha roast","Cut into strips with the fat cap on.")]),
 ("The slow cooker", "Eight hours on low.",
  [("Chuck roast","Pulls apart."),("Short ribs, boneless","Sunday-dinner rich."),("Bottom round roast","Holds a slice.")]),
 ("Korean or Japanese style grilling", "Thin cuts, sweet-salty marinades, minutes on the grill.",
  [("Korean style rib","Galbi, cut across the bones."),("Shaved ribeye","Bulgogi."),("Flank steak","Bulgogi too, sliced thin."),("Denver steak","Zabuton, sliced and grilled.")]),
 ("Chicken fried steak, Swiss steak", "Lean cuts that want breading or a long braise.",
  [("Cubed steak","Chicken fried steak."),("Bottom round steak","Swiss steak in tomato."),("Minute steak","Steak and eggs.")]),
 ("Making jerky", "Lean, sliced thin, dried low.",
  [("Beef jerky meat","Already sliced for it."),("Eye round roast","Slice it yourself."),("Top round roast","The other jerky cut.")]),
]

BASICS = [
 ("Pull temperatures", "Take steaks off a few degrees early; they climb while resting. Rare 120 to 125. Medium rare 130 to 135. Medium 140 to 145. Medium well 150 to 155. Well 160 and up. Ground beef is 160, always."),
 ("Rest it", "Five to ten minutes for a steak, twenty to thirty for a roast. Cut early and the juice ends up on the board."),
 ("Slice against the grain", "Look at which way the fibers run and cut across them. It matters most on flank, skirt, hanger, flat iron, and tri-tip."),
 ("Salt timing", "Salt 45 minutes ahead or right before it hits the heat, not in between. In between, the salt pulls moisture out and hasn't had time to go back in."),
 ("Thick versus thin", "Under an inch and a half: hot pan or grill, a few minutes a side. Thicker: reverse sear (low oven until 115 inside, then a hard sear)."),
 ("Fat is flavor", "Marbled cuts like ribeye eat best at medium rare to medium, when the fat has melted. Lean cuts like filet and anything from the round dry out past medium."),
 ("How much to buy", "About half a pound per person boneless, three quarters to a pound bone-in, a little more if you want leftovers."),
]

COW = r'''<svg viewBox="0 0 420 240" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="cowtitle">
<title id="cowtitle">Side view of a steer divided into the main cuts. Tap a section.</title>
<defs><clipPath id="body"><path d="M70 66 Q125 34 210 40 Q330 40 376 68 Q384 110 378 154 Q300 168 210 162 Q120 170 74 152 Q64 110 70 66 Z"/></clipPath></defs>
<g class="neutral">
 <path d="M14 82 Q30 60 62 62 L74 74 L72 118 Q50 130 22 122 Q6 104 14 82 Z"/>
 <path d="M56 62 L64 44 L76 60 Z"/>
 <path d="M374 70 Q396 76 392 100 L386 152 L378 152 Z"/>
</g>
<g clip-path="url(#body)">
<g class="primal" data-p="chuck" tabindex="0" role="button" aria-label="Chuck"><path d="M60 30 L146 30 L146 128 L60 128 Z"/><text x="108" y="94">Chuck</text></g>
<g class="primal" data-p="rib" tabindex="0" role="button" aria-label="Rib"><path d="M146 30 L208 30 L208 112 L146 112 Z"/><text x="177" y="84">Rib</text></g>
<g class="primal" data-p="loin" tabindex="0" role="button" aria-label="Short loin"><path d="M208 30 L266 30 L266 112 L208 112 Z"/><text x="237" y="80">Short</text><text x="237" y="94">loin</text></g>
<g class="primal" data-p="sirloin" tabindex="0" role="button" aria-label="Sirloin"><path d="M266 30 L320 30 L320 116 L266 116 Z"/><text x="293" y="86">Sirloin</text></g>
<g class="primal" data-p="round" tabindex="0" role="button" aria-label="Round"><path d="M320 30 L390 30 L390 170 L320 170 Z"/><text x="348" y="108">Round</text></g>
<g class="primal" data-p="brisket" tabindex="0" role="button" aria-label="Brisket"><path d="M60 128 L146 128 L146 170 L60 170 Z"/><text x="104" y="146">Brisket</text></g>
<g class="primal" data-p="plate" tabindex="0" role="button" aria-label="Plate"><path d="M146 112 L208 112 L208 170 L146 170 Z"/><text x="177" y="141">Plate</text></g>
<g class="primal" data-p="flank" tabindex="0" role="button" aria-label="Flank"><path d="M208 112 L320 116 L320 170 L208 170 Z"/><text x="264" y="142">Flank</text></g>
</g>
<g class="primal" data-p="shank" tabindex="0" role="button" aria-label="Shank"><path d="M100 162 L134 162 L130 222 Q114 228 100 222 Z"/><path d="M328 152 L366 150 L364 222 Q348 228 332 222 Z"/><text x="116" y="198">Shank</text><text x="347" y="195">Shank</text></g>
</svg>'''

CSS = r"""
.wrap{max-width:640px;margin:0 auto;padding:16px 16px 0}
.chartcard{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 12px 12px}
.chartcard svg{width:100%;height:auto;display:block}
.chart .neutral path{fill:#e6dad3;stroke:#fff;stroke-width:2}
.chart .primal path{fill:var(--tint);stroke:#fff;stroke-width:2;cursor:pointer;transition:fill .12s}
.chart .primal:hover path{fill:#eadbd3}
.chart .primal.on path{fill:var(--brown)}
.chart .primal text{font:600 12px var(--sans);fill:var(--brown);text-anchor:middle;pointer-events:none}
.chart .primal.on text{fill:#fff}
.chart .primal:focus{outline:none}
.chart .primal:focus-visible path{stroke:var(--brown);stroke-width:3}
@media(prefers-reduced-motion:reduce){.chart .primal path{transition:none}}
.blurb{margin:8px 4px 0;font-size:15.5px;line-height:1.5;color:var(--muted)}
.blurb b{color:var(--ink)}
.tabs{display:flex;gap:6px;margin:14px 0 12px}
.tabs button{flex:1;padding:11px 4px;border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--ink);font:500 14px var(--sans);cursor:pointer}
.tabs button[aria-selected=true]{background:var(--brown);border-color:var(--brown);color:#fff;font-weight:600}
.tabs button:focus-visible{outline:3px solid var(--brown);outline-offset:2px}
.tab[hidden]{display:none}
.btools .row{display:flex;gap:10px;align-items:center}
.btools .search{flex:1}
.bchips{display:flex;flex-wrap:wrap;gap:6px;padding:10px 0 4px}
.bchips button{padding:6px 12px;border:1px solid var(--brown);background:#fff;color:var(--brown);font:600 13px var(--sans);border-radius:999px;cursor:pointer}
.bchips button[aria-pressed=true]{background:var(--brown);color:#fff}
.bchips button:focus-visible{outline:3px solid var(--brown);outline-offset:2px}
#blist{margin-top:10px}
#blist .item{background:#fff;border:1px solid var(--line);border-top:4px dashed var(--brown);border-radius:8px;margin:0 0 10px;padding:0 12px}
#blist .item summary,#blist .item.plain{padding:12px 0}
#blist .name{font:600 20px/1.2 var(--serif)}
#blist .item.plain .name{font-weight:400}
#blist .body{margin:0 0 12px}
.section h2{margin:0 0 4px;font:400 26px/1.15 var(--serif)}
.section .sub{margin:0 0 14px;color:var(--muted);font-size:15px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px 6px;margin-bottom:10px}
.panel h3{margin:0 0 4px;font:400 22px/1.2 var(--serif)}
.panel p{margin:0 0 10px;font-size:15px;color:var(--muted)}
.picks{list-style:none;margin:0 0 6px;padding:0}
.picks li{display:flex;gap:10px;align-items:baseline;padding:8px 0;border-top:1px solid var(--line)}
.picks li:first-child{border-top:0}
.picks .cut{color:var(--brown);font-weight:600;cursor:pointer;white-space:nowrap;text-decoration:underline}
.picks span:not(.cut){color:var(--muted);font-size:14px}
.chips.wrap2{flex-wrap:wrap;overflow:visible;padding:0 0 6px}
.pick{display:none}.pick.on{display:block}
.cmp{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px}
.cmp select{width:100%;padding:10px 8px;border:1.5px solid #b9a79b;border-radius:6px;background:#fff;font:15px var(--sans);color:var(--ink)}
.cmp select:focus{outline:3px solid var(--brown);outline-offset:1px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.col{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px 8px}
.col h3{margin:0 0 6px;font:400 20px/1.2 var(--serif)}
.col h4{margin:8px 0 2px;font:600 12.5px var(--sans);color:var(--muted)}
.col p{margin:0;font-size:14px;line-height:1.45}
.col .cut{display:inline-block;margin-top:10px;font-size:13.5px;color:var(--brown);text-decoration:underline;cursor:pointer}
.basics{list-style:none;margin:0;padding:0}
.basics li{padding:12px 0;border-top:1px solid var(--line)}
.basics li:first-child{border-top:0}
.basics b{display:block;margin-bottom:2px}
.basics span{color:var(--muted);font-size:15px}
@media(max-width:480px){.cols{grid-template-columns:1fr}.tabs button{font-size:13px;padding:10px 2px}}
/* ---------- desktop (1024px and up): the original site's look, with the chart pinned on
   the left and the tabs, cuts, comparator and basics beside it. ---------- */
@media(min-width:1024px){
  .wrap{max-width:1160px;padding:40px 24px 0;display:grid;grid-template-columns:380px minmax(0,1fr);gap:0 48px;align-items:start}
  .chartcard{grid-column:1;grid-row:1/span 20;position:sticky;top:24px;background:var(--tint);border:0;border-radius:0;padding:24px 22px 20px}
  .chart .primal path{fill:#fff}
  .chart .primal:hover path{fill:#ecdcd4}
  .chart .neutral path{fill:#e3d6cf}
  .blurb{font-size:15px;line-height:24px;margin:14px 2px 0;color:#5e5e5e}
  .tabs,.tab{grid-column:2}
  .tabs{margin:0 0 6px;gap:32px;border-bottom:1px solid var(--line)}
  .tabs button{flex:none;border:0;border-bottom:1px solid transparent;margin-bottom:-1px;border-radius:0;background:none;color:#151515;padding:0 0 10px;font:400 14px/24px var(--sans);letter-spacing:.214em;text-transform:uppercase}
  .tabs button[aria-selected=true]{background:none;color:#151515;font-weight:400;border-bottom-color:var(--brown)}
  .tabs button:hover{border-bottom-color:#cdb9ab}
  .btools{padding-top:18px}
  .btools .row{max-width:520px}
  .bchips{gap:10px 26px;padding:18px 0 4px}
  .bchips button{border:0;border-bottom:1px solid transparent;border-radius:0;background:none;color:#151515;padding:0 0 4px;font:400 13px/22px var(--sans);letter-spacing:.18em;text-transform:uppercase}
  .bchips button[aria-pressed=true]{background:none;color:#151515;border-bottom-color:var(--brown)}
  .bchips button:hover{border-bottom-color:#cdb9ab}
  #blist{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px 32px;margin-top:26px;align-items:start}
  #blist .item{margin:0;padding:0;border:0;border-radius:0;background:var(--tint)}
  #blist .item summary,#blist .item.plain{padding:26px 22px 24px;min-height:148px}
  #blist .name,#blist .item.plain .name{font:400 20px/1.35 var(--sans);letter-spacing:.045em}
  #blist .body{margin:0 22px 22px}
  .section{padding-top:22px}
  .section h2{margin:0 0 6px;font:400 24px/1.4 var(--sans);letter-spacing:.125em;text-transform:uppercase;color:var(--brown)}
  .section .sub{font-size:16px;line-height:24px;color:#5e5e5e;margin:0 0 22px}
  .chips.wrap2{gap:10px 26px;padding:0 0 18px}
  .chips.wrap2 button{border:0;border-bottom:1px solid transparent;border-radius:0;background:none;color:#151515;padding:0 0 4px;font:400 13px/22px var(--sans);letter-spacing:.18em;text-transform:uppercase}
  .chips.wrap2 button[aria-pressed=true]{border-bottom-color:var(--brown)}
  .panel{background:var(--tint);border:0;border-radius:0;padding:26px 28px 16px}
  .panel h3{font:400 20px/1.35 var(--sans);letter-spacing:.045em;margin:0 0 6px}
  .panel p{font-size:15px;line-height:24px;color:#5e5e5e}
  .picks li{border-top-color:#ead9d1}
  .cmp{gap:24px;margin-bottom:24px}
  .cmp select{border:1px solid #c7c3c1;border-radius:0;padding:12px 12px;font-size:16px}
  .cols{gap:24px}
  .col{background:var(--tint);border:0;border-radius:0;padding:26px 24px 20px}
  .col h3{font:400 20px/1.35 var(--sans);letter-spacing:.045em;margin:0 0 10px}
  .col h4{margin:14px 0 4px;font:400 11.5px/1.4 var(--sans);letter-spacing:.18em;text-transform:uppercase;color:var(--brown)}
  .col p{font-size:15px;line-height:24px;color:#454545}
  .basics li{padding:18px 0;border-top-color:var(--line)}
  .basics b{font:400 18px/1.4 var(--sans);letter-spacing:.045em;margin-bottom:4px}
  .basics span{font-size:15px;line-height:24px;color:#5e5e5e}
}
"""

BEEF_CATS = ("Beef", "Ground & burgers", "Bones & broth")

HEAD_BLOCK = """<div class="head"><div class="in">
<p class="eyebrow">Emery's Meat &amp; Produce, Brewer</p>
<h1>Beef at Emery's</h1>
<p class="lede">Tap a part of the animal to see what comes from it, or search for a cut, a dish, or a word like tacos.</p>
</div></div>"""

SCRIPT = r"""
var prim=[].slice.call(document.querySelectorAll('.chart .primal')),blurb=document.getElementById('blurb'),blurbs=JSON.parse(document.getElementById('blurbdata').textContent);
var bq=document.getElementById('bq'),bchips=document.getElementById('bchips'),blist=document.getElementById('blist'),bempty=document.getElementById('bempty');
var bitems=[].slice.call(blist.querySelectorAll('.item'));
var bprimal='';
function bnorm(t){return t.replace(/-/g,' ').replace(/\s+/g,' ');}
bitems.forEach(function(el,i){el._i=i;el._n=bnorm(el.dataset.name);el._a=bnorm(el.dataset.aka);el._all=bnorm(el.dataset.search);});
function bscore(el,s){
  if(!s)return 1;
  var words=s.split(' ');
  for(var i=0;i<words.length;i++){if(el._all.indexOf(words[i])<0)return 0;}
  if(el._n===s)return 100; if(el._n.indexOf(s)===0)return 90; if((' '+el._n).indexOf(' '+s)>-1)return 80; if(el._n.indexOf(s)>-1)return 70;
  if(el._a.indexOf(s)>-1)return 50; return 10;
}
function bapply(){
  var s=bnorm(bq.value.trim().toLowerCase()),n=0;
  var ranked=bitems.map(function(el){return {el:el,sc:(!bprimal||el.dataset.primal===bprimal)?bscore(el,s):0};})
    .filter(function(x){return x.sc>0;}).sort(function(a,b){return b.sc-a.sc||a.el._i-b.el._i;});
  bitems.forEach(function(el){el.hidden=true;});
  if(s){ranked.forEach(function(x){blist.appendChild(x.el);});}
  else{bitems.slice().sort(function(a,b){return a._i-b._i;}).forEach(function(el){blist.appendChild(el);});}
  ranked.forEach(function(x){x.el.hidden=false;n++;});
  bempty.hidden=n>0;
  if(s&&n<=3){ranked.forEach(function(x){if(x.el.tagName==='DETAILS')x.el.open=true;});}
}
function selectPrimal(k,scroll){
  bprimal=k||'';
  prim.forEach(function(g){g.classList.toggle('on',g.dataset.p===bprimal);});
  [].forEach.call(bchips.children,function(x){x.setAttribute('aria-pressed',x.dataset.p===bprimal?'true':'false');});
  blurb.innerHTML=blurbs[bprimal]||blurbs[''];
  showTab('cuts'); bapply();
  if(scroll){document.getElementById('chart').scrollIntoView({block:'start'});}
}
prim.forEach(function(g){
  g.addEventListener('click',function(){selectPrimal(g.dataset.p===bprimal?'':g.dataset.p,false);});
  g.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();g.click();}});
});
bchips.addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;selectPrimal(b.dataset.p,false);});
bq.addEventListener('input',function(){if(bprimal&&bq.value.trim()){bprimal='';prim.forEach(function(g){g.classList.remove('on');});[].forEach.call(bchips.children,function(x){x.setAttribute('aria-pressed',x.dataset.p===''?'true':'false');});blurb.innerHTML=blurbs[''];}bapply();});
var tabs=[].slice.call(document.querySelectorAll('.tabs [role=tab]'));
function showTab(name){
  tabs.forEach(function(t){t.setAttribute('aria-selected',t.dataset.tab===name?'true':'false');});
  ['cuts','compare','buy','basics'].forEach(function(n){document.getElementById('tab-'+n).hidden=n!==name;});
}
tabs.forEach(function(t){t.addEventListener('click',function(){showTab(t.dataset.tab);});});
function openCut(id){
  showTab('cuts'); bq.value=''; selectPrimal('',false);
  var t=document.getElementById(id); if(!t)return;
  if(t.tagName==='DETAILS')t.open=true;
  setTimeout(function(){t.scrollIntoView({block:'start'});window.scrollBy(0,-12);},50);
}
document.addEventListener('click',function(e){var c=e.target.closest('[data-cut]');if(c){openCut(c.dataset.cut);}});
document.addEventListener('keydown',function(e){if((e.key==='Enter'||e.key===' ')&&e.target.closest&&e.target.closest('[data-cut]')){e.preventDefault();openCut(e.target.closest('[data-cut]').dataset.cut);}});
var scen=document.getElementById('scen');
scen.addEventListener('click',function(e){
  var b=e.target.closest('button');if(!b)return;
  var on=b.getAttribute('aria-pressed')==='true';
  [].forEach.call(scen.children,function(x){x.setAttribute('aria-pressed','false');});
  [].forEach.call(document.querySelectorAll('.pick'),function(p){p.classList.remove('on');});
  if(!on){b.setAttribute('aria-pressed','true');var p=document.getElementById(b.dataset.pick);p.classList.add('on');p.scrollIntoView({block:'nearest'});}
});
var data=JSON.parse(document.getElementById('cmpdata').textContent),A=document.getElementById('cmpA'),B=document.getElementById('cmpB'),out=document.getElementById('cmpOut');
function escb(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function col(n){var d=data[n];if(!d)return '';
  return '<div class="col"><h3>'+escb(n)+'</h3>'+(d.what?'<h4>What it is</h4><p>'+escb(d.what)+'</p>':'')+(d.taste?'<h4>Tastes like</h4><p>'+escb(d.taste)+'</p>':'')+(d.how?'<h4>How to cook it</h4><p>'+escb(d.how)+'</p>':'')+'<span class="cut" role="button" tabindex="0" data-cut="'+d.id+'">More on this cut</span></div>';}
function cmp(){out.innerHTML=col(A.value)+col(B.value);}
A.addEventListener('change',cmp);B.addEventListener('change',cmp);
A.value=__FIRST__;B.value=__SECOND__;cmp();
var bnote=document.getElementById('bpricenote');
if(typeof setPrices!=='function'){
  var bsw=document.querySelector('#tab-cuts .switch');
  if(bsw){bsw.addEventListener('click',function(){var on=bsw.getAttribute('aria-checked')!=='true';bsw.setAttribute('aria-checked',on?'true':'false');document.body.classList.toggle('prices',on);bnote.hidden=!on;});}
  else{bnote.hidden=!document.querySelector('#blist .price');}
}else{
  new MutationObserver(function(){bnote.hidden=!document.body.classList.contains('prices');}).observe(document.body,{attributes:true,attributeFilter:['class']});
  bnote.hidden=!document.body.classList.contains('prices');
}
try{var bh=location.hash.slice(1);if(bh&&bh.indexOf('/')<0&&blurbs[bh]!==undefined){selectPrimal(bh,false);}}catch(e){}
"""

def build_beef(rows, demo=False):
    from build import process_photos, item_html
    rows = public_rows(rows, show_all=demo)
    by_name = {r["name"]: r for r in rows}
    beef = [r for r in rows if r["cat"] in BEEF_CATS]
    for r in beef:
        r["primal"] = PRIMAL_OF.get(r["name"], "other")

    order = list(PRIMALS.keys()) + ["other"]
    cards = ""
    for key in order:
        for r in sorted((x for x in beef if x["primal"] == key), key=lambda x: x["name"].lower()):
            gallery, thumb = process_photos(r)
            cards += item_html(r, gallery, thumb, id_prefix="b-", chart_link=False, extra=f'data-primal="{key}"')
    chips = '<button type="button" aria-pressed="true" data-p="">All</button>' + "".join(
        f'<button type="button" aria-pressed="false" data-p="{k}">{esc(PRIMALS[k][0] if k != "other" else "Ground & other")}</button>'
        for k in order if any(r["primal"] == k for r in beef))
    blurbs = {k: f"<b>{esc(PRIMALS[k][0])}.</b> {esc(PRIMALS[k][1])}" for k in PRIMALS}
    blurbs["other"] = "<b>Ground and other.</b> House grinds, burger blends, and the odds and ends that don't sit on the chart."
    blurbs[""] = "Tap a part of the animal to see what comes from it."

    schips, picks = "", ""
    for i, (title, why, items) in enumerate(SCENARIOS):
        items = [(n, w) for n, w in items if n in by_name]
        if not items:
            continue
        schips += f'<button type="button" data-pick="s{i}" aria-pressed="false">{esc(title)}</button>'
        lis = "".join(f'<li><span class="cut" role="button" tabindex="0" data-cut="b-{slug(n)}">{esc(n)}</span><span>{esc(w)}</span></li>' for n, w in items)
        picks += f'<div class="panel pick" id="s{i}"><h3>{esc(title)}</h3><p>{esc(why)}</p><ul class="picks">{lis}</ul></div>'

    cmp = {r["name"]: {"what": r.get("what",""), "taste": r.get("taste",""), "how": r.get("how",""), "id": "b-" + slug(r["name"])}
           for r in beef if r.get("what")}
    opts = "".join(f'<option value="{esc(n)}">{esc(n)}</option>' for n in sorted(cmp))
    first, second = ("Porterhouse", "T-bone") if "Porterhouse" in cmp and "T-bone" in cmp else (sorted(cmp)[:2] + ["", ""])[:2]

    switch = ('<button type="button" class="switch" role="switch" aria-checked="false"><span class="knob" aria-hidden="true"></span>Prices</button>' if demo else "")
    basics = "".join(f"<li><b>{esc(t)}</b><span>{esc(b)}</span></li>" for t, b in BASICS)

    content = f'''<div class="wrap">
<div class="chartcard chart" id="chart">{COW}<p class="blurb" id="blurb">{blurbs[""]}</p></div>
<div class="tabs" role="tablist">
<button type="button" role="tab" aria-selected="true" data-tab="cuts">Cuts</button>
<button type="button" role="tab" aria-selected="false" data-tab="compare">Compare</button>
<button type="button" role="tab" aria-selected="false" data-tab="buy">What to buy</button>
<button type="button" role="tab" aria-selected="false" data-tab="basics">Basics</button>
</div>
<div class="tab btools" id="tab-cuts">
<div class="row"><label class="search"><span class="vh">Search beef</span><input type="search" id="bq" placeholder="Search a cut, a dish, or a word like tacos" autocomplete="off"></label>{switch}</div>
<div class="bchips" id="bchips">{chips}</div>
<p class="pricenote" id="bpricenote" hidden>Per pound unless noted. Prices change with the market; call to confirm.</p>
<div id="blist">{cards}</div>
<p class="empty" id="bempty" hidden>Nothing matches that. Try another word, or call the shop at (207) 922-2673.</p>
</div>
<div class="tab section" id="tab-compare" hidden>
<h2>Compare two cuts</h2>
<p class="sub">Porterhouse or T-bone? Ribeye or strip? Put any two next to each other.</p>
<div class="cmp"><select id="cmpA" aria-label="First cut">{opts}</select><select id="cmpB" aria-label="Second cut">{opts}</select></div>
<div class="cols" id="cmpOut"></div>
</div>
<div class="tab section" id="tab-buy" hidden>
<h2>What are you cooking?</h2>
<p class="sub">Pick one and we'll point you at the right cuts.</p>
<div class="chips wrap2" id="scen">{schips}</div>
{picks}
</div>
<div class="tab section" id="tab-basics" hidden>
<h2>The basics</h2>
<p class="sub">The seven things that make the biggest difference at home.</p>
<ul class="basics">{basics}</ul>
</div>
</div>
<script type="application/json" id="cmpdata">{json.dumps(cmp)}</script>
<script type="application/json" id="blurbdata">{json.dumps(blurbs)}</script>'''

    script = SCRIPT.replace("__FIRST__", json.dumps(first)).replace("__SECOND__", json.dumps(second))
    logo, ld = logo_and_ld(demo)
    return shell(title="Beef cuts", desc="A tappable chart of where each beef cut comes from, what to buy for what you're cooking, and how two cuts compare, from Emery's Meat & Produce in Brewer, Maine.",
                 head_block=HEAD_BLOCK, content=content, script=script, extra_css=CSS, active="beef", logo=logo, ld=ld,
                 footnote="Cuts and availability change with what comes in from the farms.", bodyclass="" if demo else "prices")

# ---------- single-file demo: both pages in one document, switched by hash ----------
ROUTER = r'''
var views={carry:document.getElementById('view-carry'),beef:document.getElementById('view-beef')};
function route(h){
  h=h||''; if(h.charAt(0)==='#')h=h.slice(1);
  var which=h.indexOf('beef')===0?'beef':'carry', sub=h.indexOf('/')>-1?h.slice(h.indexOf('/')+1):'';
  views.carry.hidden=which!=='carry'; views.beef.hidden=which!=='beef';
  [].forEach.call(document.querySelectorAll('[data-go="carry"],[data-go="beef"]'),function(a){
    if(a.getAttribute('data-go')===which)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  if(!menu.hidden)openMenu(false);
  if(which==='beef'){if(sub)selectPrimal(sub,true);else window.scrollTo(0,0);}
  else if(sub){openItem(sub);}
  else if(h!=='prices'){window.scrollTo(0,0);}
}
function go(h){try{history.replaceState(null,'','#'+h);}catch(e){}route(h);}
document.addEventListener('click',function(e){
  var a=e.target.closest('[data-go]'); if(!a)return;
  e.preventDefault(); e.stopPropagation(); go(a.getAttribute('data-go'));
},true);
document.addEventListener('keydown',function(e){
  if(e.key!=='Enter'&&e.key!==' ')return;
  var a=e.target.closest&&e.target.closest('[data-go]'); if(!a)return;
  e.preventDefault(); go(a.getAttribute('data-go'));
});
window.addEventListener('hashchange',function(){try{route(location.hash);}catch(e){}});
var start=''; try{start=location.hash;}catch(e){}
route(start);
'''

def build_demo(rows, index_html, beef_html):
    import re
    def view(html):
        a = html.index('<div class="head">'); z = html.index('<footer class="foot">')
        return html[a:z]
    def script(html):
        a = html.rindex('<script>\n(function(){') + len('<script>\n(function(){'); z = html.rindex('})();\n</script>')
        return html[a:z]
    def extra_css(html):
        a = html.index('.wrap{max-width'); z = html.index('</style>')
        return html[a:z]
    carry, beef = view(index_html), view(beef_html)
    page = index_html.replace(carry, f'<div class="view" id="view-carry">{carry}</div><div class="view" id="view-beef" hidden>{beef}</div>')
    page = page.replace('</style>', extra_css(beef_html) + '</style>', 1)
    page = re.sub(r'href="index\.html#([^"]+)"', r'data-go="carry/\1" role="link" tabindex="0"', page)
    page = re.sub(r'href="beef\.html#([^"]+)"', r'data-go="beef/\1" role="link" tabindex="0"', page)
    page = page.replace('href="index.html"', 'data-go="carry" role="link" tabindex="0"').replace('href="beef.html"', 'data-go="beef" role="link" tabindex="0"')
    page = page.replace('</style>', 'a[data-go]{cursor:pointer;text-decoration:underline}\n.menu a[data-go],.cuts a[data-go],.picks a[data-go],.site nav a[data-go]{text-decoration:none}\n</style>', 1)
    combined = script(index_html) + '\n' + script(beef_html) + '\n' + ROUTER
    cut = page.rindex('<script>\n(function(){') + len('<script>\n(function(){')
    return page[:cut] + combined + page[page.rindex('})();\n</script>'):]
