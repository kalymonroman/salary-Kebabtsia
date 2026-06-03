"""
Веб-панель адміна для обліку зарплати
"""
import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, session

app = Flask(__name__)
app.secret_key = os.getenv("WEBAPP_SECRET", "salary-panel-2026")
WEBAPP_PASSWORD = os.getenv("WEBAPP_PASSWORD", "admin123")

MONTHS_UA = ["","Січень","Лютий","Березень","Квітень","Травень","Червень",
             "Липень","Серпень","Вересень","Жовтень","Листопад","Грудень"]

def get_db():
    from db import DB
    return DB()

def parse_month(month_str):
    try:
        parts = month_str.split("-")
        return int(parts[0]), int(parts[1])
    except Exception:
        now = datetime.now()
        return now.year, now.month

def get_entries_for_user(db, tid, loc, m, y):
    role = db.get_role(tid)
    if not role:
        return None, None
    if role["role"] == "location_admin":
        locs = db.get_admin_locations(tid)
        if not locs:
            return role, []
        if loc and loc in locs:
            entries = db.get_location_entries(loc, m, y)
        else:
            entries = []
            for l in locs:
                entries.extend(db.get_location_entries(l, m, y))
    elif loc:
        entries = db.get_location_entries(loc, m, y)
    else:
        entries = db.get_all_entries(m, y)
    return role, entries

HTML = r"""<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Облік зарплати</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f1117;color:#e8e8e8;min-height:100vh;font-size:13px}
.topbar{background:#1a1d27;border-bottom:1px solid #2a2d3a;padding:10px 16px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;position:sticky;top:0;z-index:100}
.topbar-title{font-size:14px;font-weight:500;color:#fff}
.ctrl{display:flex;gap:6px;align-items:center;flex:1;flex-wrap:wrap}
select,input[type=text],input[type=password],input[type=number]{background:#2a2d3a;border:1px solid #3a3d4a;color:#e8e8e8;padding:6px 9px;border-radius:8px;font-size:12px;outline:none}
select:focus,input:focus{border-color:#3b6ef0}
.nav-tabs{display:flex;background:#1a1d27;border-bottom:1px solid #2a2d3a;padding:0 16px}
.ntab{padding:10px 16px;font-size:13px;color:#8b8fa8;cursor:pointer;border-bottom:2px solid transparent;transition:all .15s}
.ntab.active{color:#fff;border-bottom-color:#3b6ef0}
.main{padding:14px 16px}
.filter-row{display:flex;gap:5px;margin-bottom:10px;flex-wrap:wrap}
.ftab{font-size:11px;padding:4px 10px;border-radius:20px;border:1px solid #3a3d4a;cursor:pointer;color:#8b8fa8;background:#1a1d27}
.ftab.active{background:#3b6ef0;color:#fff;border-color:#3b6ef0}
.stat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px}
.stat{background:#1a1d27;border:1px solid #2a2d3a;border-radius:10px;padding:9px 12px}
.stat-l{font-size:10px;color:#6b6f7e;margin-bottom:2px}
.stat-v{font-size:15px;font-weight:500;color:#fff}
.stat-s{font-size:10px;color:#4a4f60}
.table-wrap{background:#1a1d27;border:1px solid #2a2d3a;border-radius:10px;overflow:auto;margin-bottom:70px}
table{width:100%;border-collapse:collapse;min-width:800px}
thead th{background:#22253a;padding:8px 10px;text-align:right;font-weight:500;color:#8b8fa8;border-bottom:1px solid #2a2d3a;white-space:nowrap;cursor:pointer;user-select:none;font-size:12px}
thead th:first-child,thead th:nth-child(2){text-align:left}
thead th:hover{color:#e8e8e8}
tbody td{padding:7px 10px;border-bottom:1px solid #1e2130;text-align:right;vertical-align:middle}
tbody td:first-child,tbody td:nth-child(2){text-align:left}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover{background:#1e2234}
tbody tr.changed{background:#1a2040}
tfoot td{padding:8px 10px;text-align:right;font-weight:500;background:#1e3060;color:#7aafff;border-top:2px solid #3b6ef0;font-size:12px}
tfoot td:first-child,tfoot td:nth-child(2){text-align:left}
.cb{width:17px;height:17px;cursor:pointer;accent-color:#3b6ef0}
.cb-cell{text-align:center!important}
.muted{color:#6b6f7e;font-size:11px}
.total-cell{font-weight:500;color:#e8e8e8}
.dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#3b6ef0;margin-left:4px;vertical-align:middle}
.save-bar{position:fixed;bottom:0;left:0;right:0;background:#1a2040;border-top:1px solid #3b6ef0;padding:10px 16px;display:flex;align-items:center;gap:10px;transform:translateY(100%);transition:transform .3s;z-index:200}
.save-bar.show{transform:translateY(0)}
.btn{padding:7px 16px;border-radius:8px;border:1px solid #3a3d4a;cursor:pointer;font-size:12px;font-weight:500;background:#2a2d3a;color:#e8e8e8}
.btn-primary{background:#3b6ef0;color:#fff;border-color:#3b6ef0}
.btn-sm{padding:5px 10px;font-size:11px}
.toast{position:fixed;top:16px;right:16px;padding:10px 16px;border-radius:8px;font-size:13px;z-index:300;transition:opacity .3s;opacity:0;pointer-events:none}
.toast.ok{background:#1a3a2a;border:1px solid #2a6040;color:#4adf8a}
.toast.err{background:#3a1a1a;border:1px solid #6a2020;color:#ff6b6b}
.toast.show{opacity:1}
.login-wrap{display:flex;align-items:center;justify-content:center;min-height:100vh}
.login-box{background:#1a1d27;border:1px solid #2a2d3a;border-radius:16px;padding:32px;width:320px}
.login-box h2{font-size:18px;font-weight:500;margin-bottom:6px;color:#fff;text-align:center}
.login-box p{font-size:12px;color:#6b6f7e;text-align:center;margin-bottom:20px}
.login-box input{width:100%;display:block;margin-bottom:10px}
.login-box .btn-primary{width:100%;padding:9px;margin-top:4px}
.login-err{color:#ff6b6b;font-size:11px;margin-top:6px;min-height:16px}
.role-badge{font-size:10px;padding:2px 8px;border-radius:10px;font-weight:500;background:#1a2a50;color:#5a8aff}
.screen{display:none}.screen.active{display:block}
.stab{font-size:11px;padding:4px 10px;border-radius:20px;border:1px solid #3a3d4a;cursor:pointer;color:#8b8fa8;background:#1a1d27}
.stab.active{background:#3b6ef0;color:#fff;border-color:#3b6ef0}
@media(max-width:600px){.stat-grid{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>

{% if not logged_in %}
<div class="login-wrap">
  <div class="login-box">
    <h2>💰 Облік зарплати</h2>
    <p>Введіть свій Telegram ID та пароль</p>
    <input type="number" id="tid" placeholder="Telegram ID (числом)">
    <input type="password" id="pwd" placeholder="Пароль" onkeydown="if(event.key==='Enter')login()">
    <div class="login-err" id="err"></div>
    <button class="btn btn-primary" onclick="login()">Увійти</button>
    <p style="margin-top:12px;font-size:11px;color:#4a4f60">Дізнайтесь ID написавши @userinfobot у Telegram</p>
  </div>
</div>
<script>
function login(){
  const tid=document.getElementById('tid').value;
  const pwd=document.getElementById('pwd').value;
  if(!tid||!pwd){document.getElementById('err').textContent='Заповніть всі поля';return;}
  fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({telegram_id:tid,password:pwd})})
  .then(r=>r.json()).then(d=>{
    if(d.ok)location.reload();
    else document.getElementById('err').textContent=d.error||'Невірний пароль або ID';
  });
}
</script>
{% else %}

<div class="topbar">
  <div class="topbar-title">💰 Облік зарплати</div>
  <div class="ctrl">
    <select id="sel-month" onchange="loadAll()">
      {% for m in months %}<option value="{{ m.val }}" {% if m.active %}selected{% endif %}>{{ m.label }}</option>{% endfor %}
    </select>
    {% if show_loc_selector %}
    <select id="sel-loc" onchange="loadAll()">
      <option value="">Всі заклади</option>
      {% for loc in locations %}<option value="{{ loc }}">{{ loc }}</option>{% endfor %}
    </select>
    {% endif %}
    <input type="text" id="search" placeholder="Пошук..." style="width:130px" oninput="render()">
  </div>
  <span class="role-badge">{{ role_name }}</span>
  <button class="btn btn-sm" onclick="logout()">Вийти</button>
</div>

<div class="nav-tabs">
  <div class="ntab active" onclick="showPage('table',this)">Таблиця</div>
  <div class="ntab" onclick="showPage('stats',this)">Статистика</div>
</div>

<div class="main">

<div id="page-table" class="screen active">
  <div class="filter-row">
    <div class="ftab active" onclick="setFilter('all',this)">Всі записи</div>
    <div class="ftab" onclick="setFilter('no_univ',this)">Без університала</div>
    <div class="ftab" onclick="setFilter('no_bonus',this)">Без премії</div>
    <div class="ftab" onclick="setFilter('changed',this)">Змінені</div>
  </div>
  <div class="stat-grid">
    <div class="stat"><div class="stat-l">Записів</div><div class="stat-v" id="s-cnt">—</div></div>
    <div class="stat"><div class="stat-l">Унів. проставлено</div><div class="stat-v" id="s-univ">—</div><div class="stat-s">× 150 грн</div></div>
    <div class="stat"><div class="stat-l">Премій проставлено</div><div class="stat-v" id="s-bonus">—</div><div class="stat-s">× 200 грн</div></div>
    <div class="stat"><div class="stat-l">Сума надбавок</div><div class="stat-v" id="s-add">—</div></div>
    <div class="stat"><div class="stat-l">Загальна сума</div><div class="stat-v" id="s-total">—</div></div>
    <div class="stat"><div class="stat-l">Змінено записів</div><div class="stat-v" id="s-changed">0</div></div>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th onclick="sortBy('date')" style="text-align:left">Дата ↕</th>
        <th onclick="sortBy('name')" style="text-align:left">Працівник ↕</th>
        <th onclick="sortBy('location')">Заклад ↕</th>
        <th onclick="sortBy('hours')">Год. ↕</th>
        <th onclick="sortBy('rate')">Ставка</th>
        <th onclick="sortBy('revenue')">Виторг ↕</th>
        <th onclick="sortBy('base_pay')">База ↕</th>
        <th onclick="sortBy('rate_bonus')">Бонус каси ↕</th>
        <th class="cb-cell">🔧 Унів<br><span style="font-weight:400;font-size:10px">+150</span></th>
        <th class="cb-cell">⭐ Премія<br><span style="font-weight:400;font-size:10px">+200</span></th>
        <th onclick="sortBy('total')">Разом ↕</th>
      </tr></thead>
      <tbody id="tbody"></tbody>
      <tfoot id="tfoot"></tfoot>
    </table>
  </div>
</div>

<div id="page-stats" class="screen">
  <div style="display:flex;gap:5px;margin-bottom:12px;flex-wrap:wrap" id="stats-tabs">
    <div class="stab active" onclick="setStatsTab('loc',this)">По закладах</div>
    <div class="stab" onclick="setStatsTab('workers',this)">По працівниках</div>
  </div>
  <div id="stats-content"><div style="color:#6b6f7e;padding:20px">Перейдіть на Таблицю спочатку</div></div>
</div>

</div>

<div class="save-bar" id="save-bar">
  <span style="color:#7aafff;font-size:12px;font-weight:500" id="save-info"></span>
  <button class="btn btn-primary" onclick="saveChanges()">💾 Зберегти зміни</button>
  <button class="btn" onclick="discardChanges()">Скасувати</button>
</div>
<div class="toast" id="toast"></div>

<script>
let allData=[], statsData=null;
let changed={}, sortKey='date', sortAsc=true, filterMode='all', statsTab='loc';
const SHOW_LOC_SELECTOR={{ 'true' if show_loc_selector else 'false' }};
const USER_LOC='{{ user_location }}';

function getParams(){
  const month=document.getElementById('sel-month').value;
  const loc=SHOW_LOC_SELECTOR?(document.getElementById('sel-loc')?.value||''):USER_LOC;
  return {month,loc};
}

async function loadAll(){
  const {month,loc}=getParams();
  const r=await fetch(`/api/entries?month=${month}&loc=${encodeURIComponent(loc)}`);
  allData=await r.json();
  changed={};
  updateSaveBar();
  render();
  buildStats(allData);
}

function buildStats(data){
  const byLoc={}, byWorker={};
  data.forEach(e=>{
    const l=e.location||'?';
    const wKey=String(e.telegram_id);
    const base=parseFloat(e.base_pay)||0;
    const bonusV=parseFloat(e.rate_bonus)||0;
    const univV=parseFloat(e.universal)||0;
    const premV=parseFloat(e.bonus)||0;
    const hours=parseFloat(e.hours)||0;
    const tot=base+bonusV+univV+premV;

    if(!byLoc[l]) byLoc[l]={name:l,workers:new Set(),count:0,hours:0,base:0,bonus:0,univ:0,premium:0,total:0};
    byLoc[l].workers.add(wKey);
    byLoc[l].count++;
    byLoc[l].hours+=hours;
    byLoc[l].base+=base; byLoc[l].bonus+=bonusV;
    byLoc[l].univ+=univV; byLoc[l].premium+=premV;
    byLoc[l].total+=tot;

    if(!byWorker[wKey]) byWorker[wKey]={name:e.name,loc:l,count:0,hours:0,base:0,bonus:0,univ:0,premium:0,total:0};
    byWorker[wKey].count++;
    byWorker[wKey].hours+=hours;
    byWorker[wKey].base+=base; byWorker[wKey].bonus+=bonusV;
    byWorker[wKey].univ+=univV; byWorker[wKey].premium+=premV;
    byWorker[wKey].total+=tot;
  });

  const locList=Object.values(byLoc).map(l=>({...l,workers:l.workers.size})).sort((a,b)=>a.name.localeCompare(b.name));
  const workerList=Object.values(byWorker).sort((a,b)=>a.name.localeCompare(b.name));
  statsData={by_location:locList,by_worker:workerList};
  if(document.getElementById('page-stats').classList.contains('active')) renderStats();
}

function sortBy(key){
  if(sortKey===key)sortAsc=!sortAsc; else{sortKey=key;sortAsc=true;}
  render();
}
function setFilter(f,el){
  filterMode=f;
  document.querySelectorAll('.ftab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  render();
}
function setStatsTab(tab,el){
  statsTab=tab;
  document.querySelectorAll('.stab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  renderStats();
}
function getFiltered(){
  const q=(document.getElementById('search').value||'').toLowerCase();
  return allData.filter(r=>{
    if(q&&!r.name.toLowerCase().includes(q)&&!r.location.toLowerCase().includes(q))return false;
    const u=changed[r.row_id]?.univ??(parseFloat(r.universal||0)>0);
    const b=changed[r.row_id]?.bonus??(parseFloat(r.bonus||0)>0);
    if(filterMode==='no_univ')return !u;
    if(filterMode==='no_bonus')return !b;
    if(filterMode==='changed')return changed[r.row_id]!==undefined;
    return true;
  });
}
function fmt(n){return Math.round(n).toLocaleString('uk');}
function render(){
  let rows=getFiltered();
  rows.sort((a,b)=>{
    let av=a[sortKey]||'',bv=b[sortKey]||'';
    if(['revenue','base_pay','rate_bonus','total','hours','rate'].includes(sortKey)){av=parseFloat(av)||0;bv=parseFloat(bv)||0;}
    if(sortKey==='date'){av=a.date.split('.').reverse().join('');bv=b.date.split('.').reverse().join('');}
    return sortAsc?(av>bv?1:-1):(av<bv?1:-1);
  });
  let totBase=0,totRateB=0,totUniv=0,totBonus=0,totHours=0,grand=0;
  document.getElementById('tbody').innerHTML=rows.map(r=>{
    const isC=changed[r.row_id]!==undefined;
    const univ=changed[r.row_id]?.univ??(parseFloat(r.universal||0)>0);
    const bonus=changed[r.row_id]?.bonus??(parseFloat(r.bonus||0)>0);
    const base=parseFloat(r.base_pay||0);
    const rateB=parseFloat(r.rate_bonus||0);
    const univA=univ?150:0; const bonusA=bonus?200:0;
    const rowTot=base+rateB+univA+bonusA;
    totBase+=base;totRateB+=rateB;totUniv+=univA;totBonus+=bonusA;
    totHours+=parseFloat(r.hours||0);grand+=rowTot;
    return `<tr class="${isC?'changed':''}" id="tr-${r.row_id}">
      <td>${r.date}</td><td>${r.name}${isC?'<span class="dot"></span>':''}</td>
      <td class="muted">${r.location}</td><td class="muted">${r.hours}</td>
      <td class="muted">Ст.${r.rate}/${r.hourly_rate}грн</td>
      <td class="muted">${fmt(r.revenue)}</td><td>${fmt(base)}</td>
      <td>${rateB>0?'+'+fmt(rateB):'—'}</td>
      <td class="cb-cell"><input type="checkbox" class="cb" ${univ?'checked':''} onchange="toggle(${r.row_id},'univ',this.checked)"></td>
      <td class="cb-cell"><input type="checkbox" class="cb" ${bonus?'checked':''} onchange="toggle(${r.row_id},'bonus',this.checked)"></td>
      <td class="total-cell">${fmt(rowTot)}</td>
    </tr>`;
  }).join('');
  document.getElementById('tfoot').innerHTML=`<tr>
    <td>↓ Разом</td><td>${rows.length} записів</td><td></td>
    <td>${totHours.toFixed(1)} год</td><td></td><td></td>
    <td>${fmt(totBase)}</td><td>${totRateB>0?'+'+fmt(totRateB):'—'}</td>
    <td class="cb-cell">${totUniv>0?'+'+fmt(totUniv):'—'}</td>
    <td class="cb-cell">${totBonus>0?'+'+fmt(totBonus):'—'}</td>
    <td>${fmt(grand)}</td>
  </tr>`;
  const univCnt=rows.filter(r=>changed[r.row_id]?.univ??(parseFloat(r.universal||0)>0)).length;
  const bonusCnt=rows.filter(r=>changed[r.row_id]?.bonus??(parseFloat(r.bonus||0)>0)).length;
  document.getElementById('s-cnt').textContent=rows.length;
  document.getElementById('s-univ').textContent=univCnt;
  document.getElementById('s-bonus').textContent=bonusCnt;
  document.getElementById('s-add').textContent=fmt(univCnt*150+bonusCnt*200)+' грн';
  document.getElementById('s-total').textContent=fmt(grand)+' грн';
  document.getElementById('s-changed').textContent=Object.keys(changed).length;
}
function renderStats(){
  if(!statsData){document.getElementById('stats-content').innerHTML='<div style="color:#6b6f7e;padding:20px">Спочатку завантажте Таблицю</div>';return;}
  const rows=statsTab==='loc'?statsData.by_location:statsData.by_worker;
  if(!rows||!rows.length){document.getElementById('stats-content').innerHTML='<div style="color:#6b6f7e;padding:20px">Немає даних за цей період</div>';return;}
  const fields=['base','bonus','univ','premium'];
  const labels=['База','Бонус каси','Університал','Премії'];
  const colT={base:0,bonus:0,univ:0,premium:0,total:0,hours:0};
  rows.forEach(r=>{fields.forEach(f=>colT[f]+=(r[f]||0));colT.total+=(r.total||0);colT.hours+=(r.hours||0);});
  const firstCol=statsTab==='loc'?'Заклад':'Працівник';
  document.getElementById('stats-content').innerHTML=`
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th style="text-align:left">${firstCol}</th>
        <th>К-сть</th><th>Год.</th>
        ${labels.map(l=>`<th>${l}</th>`).join('')}
        <th>→ Разом</th>
      </tr></thead>
      <tbody>${rows.map(r=>`<tr>
        <td>${r.name}${r.loc&&r.loc!==r.name?`<br><span class="muted">${r.loc}</span>`:''}</td>
        <td class="muted" style="text-align:right">${r.count||r.workers||0}</td>
        <td class="muted" style="text-align:right">${(r.hours||0).toFixed(1)}</td>
        ${fields.map(f=>`<td>${(r[f]||0)>0?fmt(r[f]):'—'}</td>`).join('')}
        <td class="total-cell">${fmt(r.total||0)}</td>
      </tr>`).join('')}</tbody>
      <tfoot><tr>
        <td>↓ Разом</td><td></td><td>${colT.hours.toFixed(1)}</td>
        ${fields.map(f=>`<td>${fmt(colT[f])}</td>`).join('')}
        <td>${fmt(colT.total)}</td>
      </tr></tfoot>
    </table>
  </div>`;
}
function toggle(rowId,field,val){
  if(!changed[rowId])changed[rowId]={};
  changed[rowId][field]=val;
  updateSaveBar();render();
  const updatedData=allData.map(r=>{
    if(r.row_id!==rowId)return r;
    return {...r,
      universal:changed[rowId]?.univ??(parseFloat(r.universal||0)>0)?150:0,
      bonus:changed[rowId]?.bonus??(parseFloat(r.bonus||0)>0)?200:0
    };
  });
  buildStats(updatedData);
}
function updateSaveBar(){
  const n=Object.keys(changed).length;
  document.getElementById('save-bar').classList.toggle('show',n>0);
  document.getElementById('save-info').textContent=n>0?`Змінено: ${n} ${n===1?'запис':'записів'}`:'';
  document.getElementById('s-changed').textContent=n;
}
async function saveChanges(){
  const updates=Object.entries(changed).map(([rowId,fields])=>({row_id:parseInt(rowId),...fields}));
  const r=await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(updates)});
  const d=await r.json();
  if(d.ok){changed={};updateSaveBar();await loadAll();showToast('✅ Збережено в Google Sheets','ok');}
  else showToast('❌ Помилка збереження','err');
}
function discardChanges(){changed={};updateSaveBar();render();}
function showToast(msg,type){
  const t=document.getElementById('toast');
  t.textContent=msg;t.className=`toast ${type} show`;
  setTimeout(()=>t.classList.remove('show'),3000);
}
async function showPage(name,el){
  document.querySelectorAll('.ntab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('page-table').classList.toggle('active',name==='table');
  document.getElementById('page-stats').classList.toggle('active',name==='stats');
  if(name==='stats') renderStats();
}
function logout(){fetch('/api/logout',{method:'POST'}).then(()=>location.reload());}
loadAll();
</script>
{% endif %}
</body>
</html>"""


def get_months():
    now = datetime.now()
    months = []
    for i in range(6):
        m = now.month - i
        y = now.year
        if m <= 0:
            m += 12
            y -= 1
        months.append({"val": f"{y}-{m:02d}", "label": f"{MONTHS_UA[m]} {y}", "active": i == 0})
    return months


@app.route("/")
def index():
    if not session.get("logged_in"):
        return render_template_string(HTML, logged_in=False, locations=[], months=[],
                                      show_loc_selector=False, user_location="")
    from calc import LOCATIONS
    db = get_db()
    role = db.get_role(session["telegram_id"])
    role_map = {"owner": "Власник", "superadmin": "Головний адмін",
                "location_admin": "Адмін закладу", "worker": "Працівник"}
    role_name = role_map.get(role["role"], "") if role else ""
    is_superadmin = role and role["role"] in ("owner", "superadmin")
    admin_locs = db.get_admin_locations(session["telegram_id"]) if not is_superadmin else []
    is_multi_loc = len(admin_locs) > 1
    show_loc_selector = is_superadmin or is_multi_loc
    locations = LOCATIONS if is_superadmin else admin_locs
    user_location = admin_locs[0] if len(admin_locs) == 1 else ""
    return render_template_string(
        HTML, logged_in=True, locations=locations, months=get_months(),
        role_name=role_name, show_loc_selector=show_loc_selector,
        user_location=user_location,
    )


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json
    pwd = data.get("password", "")
    tid = data.get("telegram_id", "")
    if pwd != WEBAPP_PASSWORD:
        return jsonify({"ok": False, "error": "Невірний пароль"})
    try:
        tid = int(tid)
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Невірний Telegram ID"})
    db = get_db()
    role = db.get_role(tid)
    if not role or role["role"] not in ("owner", "superadmin", "location_admin"):
        return jsonify({"ok": False, "error": "Немає доступу до панелі"})
    session["logged_in"] = True
    session["telegram_id"] = tid
    return jsonify({"ok": True})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/entries")
def api_entries():
    if not session.get("logged_in"):
        return jsonify([])
    month_str = request.args.get("month", "")
    loc = request.args.get("loc", "")
    db = get_db()
    y, m = parse_month(month_str)
    tid = session["telegram_id"]
    role, entries = get_entries_for_user(db, tid, loc, m, y)
    if role is None:
        return jsonify([])
    result = []
    for e in entries:
        try:
            result.append({
                "row_id": e.get("row_id", 0),
                "telegram_id": str(e.get("telegram_id", "")),
                "name": e.get("name", ""),
                "date": e.get("date", ""),
                "location": e.get("location", ""),
                "hours": float(str(e.get("hours", 0)).replace(",", ".")),
                "rate": float(str(e.get("rate", 1)).replace(",", ".")),
                "revenue": float(str(e.get("revenue", 0)).replace(",", ".")),
                "hourly_rate": float(str(e.get("hourly_rate", 110)).replace(",", ".")),
                "base_pay": float(str(e.get("base_pay", 0)).replace(",", ".")),
                "rate_bonus": float(str(e.get("rate_bonus", 0)).replace(",", ".")),
                "universal": float(str(e.get("universal", 0)).replace(",", ".")),
                "bonus": float(str(e.get("bonus", 0)).replace(",", ".")),
                "total": float(str(e.get("total", 0)).replace(",", ".")),
            })
        except Exception:
            continue
    return jsonify(result)


@app.route("/api/save", methods=["POST"])
def api_save():
    if not session.get("logged_in"):
        return jsonify({"ok": False})
    updates = request.json
    db = get_db()
    for u in updates:
        row_id = u.get("row_id")
        if not row_id:
            continue
        try:
            entry = db.get_entry_by_row(row_id)
            if not entry:
                continue
            univ = 150.0 if u.get("univ", False) else 0.0
            bonus = 200.0 if u.get("bonus", False) else 0.0
            db.set_universal_bonus(
                int(entry["telegram_id"]), entry["date"],
                univ, bonus, row_id=row_id
            )
        except Exception:
            continue
    return jsonify({"ok": True})


@app.route("/ping")
def ping():
    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
