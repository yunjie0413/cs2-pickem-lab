import { validateEvent, predictMatch, scoreBallot } from './engine.mjs';

const $ = id => document.getElementById(id);
const esc = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const percent = value => `${(100 * value).toFixed(1)}%`;
const categories = [
  { key:'threeZero', title:'Perfect run · 3–0', capacity:2, className:'perfect' },
  { key:'ordinaryAdvance', title:'Advance · 3–1 / 3–2', capacity:6, className:'ordinary' },
  { key:'zeroThree', title:'Early exit · 0–3', capacity:2, className:'out' }
];
const storageKey = 'pickem-lab-v1';
let event, result, worker, appliedOptions;
let ballot = { threeZero:[], ordinaryAdvance:[], zeroThree:[] };
let saved;
try { saved = JSON.parse(localStorage.getItem(storageKey)); } catch { /* Storage is optional. */ }

function status(message, error = false) {
  $('status').textContent = message;
  $('status').classList.toggle('error', error);
}
function options() { return { runs:Number($('runs').value), seed:Number($('seed').value), mapWeight:Number($('map-weight').value) }; }
function save() {
  try { localStorage.setItem(storageKey, JSON.stringify({ event, ballot, options:options(), threshold:Number($('threshold').value), ordinaryIncludesPerfect:$('includes-perfect').checked })); } catch { /* Private browsing and quota limits should not block use. */ }
}
function busy(value) {
  for (const id of ['simulate','runs','seed','map-weight']) $(id).disabled = value;
  $('simulate').textContent = value ? 'Simulating…' : 'Run simulation';
  $('fill-picks').disabled = value || !result;
}
function installEvent(nextEvent, restore = false) {
  validateEvent(nextEvent);
  worker?.terminate();
  event = structuredClone(nextEvent);
  result = undefined;
  appliedOptions = undefined;
  if (!restore) ballot = { threeZero:[], ordinaryAdvance:[], zeroThree:[] };
  const ids = new Set(event.teams.map(team => team.id));
  const used = new Set();
  for (const category of categories) ballot[category.key] = (ballot[category.key] || []).filter(id => ids.has(id) && !used.has(id) && used.add(id)).slice(0, category.capacity);
  $('event-name').textContent = event.name;
  $('stage-label').textContent = `${event.stage.name} · ${event.stage.allBestOfThree ? 'ALL BO3' : 'BO1 / BO3'}`;
  const mode = event.dataMode === 'demo' ? 'Fictional demo' : 'Manual snapshot';
  const source = typeof event.source === 'string' ? event.source : 'User-provided import';
  $('snapshot').textContent = `${event.completedRounds.length} completed rounds · ${source} · Snapshot: ${event.updatedAt}`;
  $('data-notice').innerHTML = `<strong>${esc(mode)}</strong><span>${event.dataMode === 'demo' ? 'Example teams and ratings. No live feed or validated forecasts.' : 'Imported data and supplied ratings. No automatic feed; forecasts depend on your data and model assumptions.'}</span>`;
  if (!restore) $('includes-perfect').checked = Boolean(event.stage.ordinaryIncludesPerfect);
  const teamOptions = event.teams.toSorted((a,b) => a.seed-b.seed).map(team => `<option value="${esc(team.id)}">${esc(team.name)}</option>`).join('');
  $('team-a').innerHTML = teamOptions;
  $('team-b').innerHTML = teamOptions;
  $('team-b').selectedIndex = 1;
  renderMapSelects();
  renderBallot();
  renderMatchup();
  runSimulation();
}
function runSimulation() {
  if (!event) return;
  const settings = options();
  if (!Number.isInteger(settings.seed) || settings.seed < 0 || settings.seed > 4294967295) {
    status('Choose a whole-number seed between 0 and 4,294,967,295.', true);
    return;
  }
  worker?.terminate();
  result = undefined;
  $('team-rows').innerHTML = '<tr><td colspan="6">Simulating possible stage outcomes…</td></tr>';
  $('stat-runs').textContent = '—';
  $('stat-error').textContent = '—';
  renderScore();
  busy(true);
  status(`Simulating ${settings.runs.toLocaleString()} outcomes from ${event.completedRounds.length} completed rounds…`);
  worker = new Worker(new URL('./worker.mjs', import.meta.url), { type:'module' });
  worker.onmessage = ({ data }) => {
    busy(false);
    if (data.error) { status(data.error, true); return; }
    result = data.result;
    appliedOptions = settings;
    $('fill-picks').disabled = false;
    $('stat-runs').textContent = result.runs.toLocaleString();
    const worst = Math.max(...result.teams.flatMap(team => [team.threeZero,team.advance,team.ordinaryAdvance,team.zeroThree]).map(p => 1.96*Math.sqrt(p*(1-p)/result.runs)));
    $('stat-error').textContent = `±${(100*worst).toFixed(2)} pp`;
    $('stat-format').textContent = `${event.stage.allBestOfThree ? 'All BO3' : 'BO1 / BO3'} · Seed ${settings.seed} · Map weight ${Math.round(settings.mapWeight*100)}%`;
    status(`${result.runs.toLocaleString()} runs complete. Completed rounds are fixed; remaining matches are simulated. Probabilities are estimates under the supplied model.`);
    renderTable(); renderScore(); save();
    worker.terminate();
  };
  worker.onerror = error => { busy(false); status(`Simulation could not start: ${error.message}. Run this project through npm start.`, true); worker.terminate(); };
  worker.postMessage({ event, options:settings });
}
function renderTable() {
  if (!result) return;
  const field = $('sort').value;
  const byId = new Map(result.teams.map(team => [team.id,team]));
  const current = new Map(result.standings.map(team => [team.id,team]));
  const sorted = event.teams.toSorted((a,b) => field === 'seed' ? a.seed-b.seed : byId.get(b.id)[field]-byId.get(a.id)[field] || a.seed-b.seed);
  $('team-rows').innerHTML = sorted.map(team => {
    const p = byId.get(team.id), record = current.get(team.id);
    const category = categories.find(c => ballot[c.key].includes(team.id));
    const initials = team.name.split(/\s+/).map(part => part[0]).join('').slice(0,2);
    const numbers = ['threeZero','advance','ordinaryAdvance','zeroThree'].map(field => `<td><div class="prob ${field === 'advance' ? 'prob-advance' : ''}"><span class="prob-number">${percent(p[field])}</span>${field === 'advance' ? `<i class="prob-bar" style="width:${100*p[field]}%"></i>` : ''}</div></td>`).join('');
    return `<tr class="${category ? 'selected' : ''}"><td><div class="team-cell"><span class="team-logo" aria-hidden="true">${esc(initials)}</span><div><span class="team-name">${esc(team.name)}</span><span class="team-record">#${team.seed} · ${record?.wins || 0}–${record?.losses || 0}</span></div></div></td>${numbers}<td><select class="row-pick" data-team="${esc(team.id)}" aria-label="Pick category for ${esc(team.name)}"><option value="">No pick</option>${categories.map(c => `<option value="${c.key}" ${c.key === category?.key ? 'selected' : ''}>${c.key === 'threeZero' ? '3–0' : c.key === 'zeroThree' ? '0–3' : 'Advance'}</option>`).join('')}</select></td></tr>`;
  }).join('');
}
function renderBallot() {
  if (!event) return;
  $('ballot-slots').innerHTML = categories.map(category => {
    const picks = ballot[category.key];
    const title = category.key === 'ordinaryAdvance' && $('includes-perfect').checked ? 'Advance · any 3 wins' : category.title;
    const slots = Array.from({ length:category.capacity }, (_,index) => {
      const id = picks[index], team = event.teams.find(team => team.id === id);
      return team ? `<div class="pick-slot"><span>${esc(team.name)}</span><button class="remove-pick" data-remove="${esc(id)}" aria-label="Remove ${esc(team.name)}">×</button></div>` : '<div class="pick-slot empty">Choose a team</div>';
    }).join('');
    return `<div class="bucket ${category.className}"><div class="bucket-title"><span>${title}</span><small>${picks.length}/${category.capacity}</small></div><div>${slots}</div></div>`;
  }).join('');
  $('export-picks').disabled = !categories.some(c => ballot[c.key].length);
  renderScore();
}
function renderScore() {
  const threshold = Number($('threshold').value);
  $('ballot-goal').textContent = `CHANCE OF ${threshold}+ CORRECT`;
  if (!result) {
    $('stat-success').textContent = '—';
    $('stat-ballot').textContent = 'Run a simulation to evaluate your picks';
    $('histogram').innerHTML = '';
    $('ballot-errors').textContent = '';
    return;
  }
  const score = scoreBallot(result, ballot, { threshold, ordinaryIncludesPerfect:$('includes-perfect').checked });
  if (!score.valid) {
    $('stat-success').textContent = '—';
    const count = categories.reduce((sum,c) => sum+ballot[c.key].length,0);
    $('stat-ballot').textContent = `${count}/10 slots filled · complete your ballot`;
    $('histogram').innerHTML = '';
    $('ballot-errors').textContent = count ? 'Choose 2 perfect runs, 6 advances and 2 early exits.' : '';
    return;
  }
  $('ballot-errors').textContent = '';
  $('stat-success').textContent = percent(score.successProbability);
  const margin = 196*Math.sqrt(score.successProbability*(1-score.successProbability)/result.runs);
  $('stat-ballot').textContent = `${score.expectedCorrect.toFixed(2)} expected correct · MC error ≈ ±${margin.toFixed(2)} pp`;
  const max = Math.max(...score.distribution, 0.001);
  $('histogram').innerHTML = score.distribution.map((p,k) => `<div class="hist-col ${k >= threshold ? 'pass' : ''}" style="height:${Math.max(2,p/max*76)}px" title="${k} correct: ${percent(p)}"><span>${k}</span></div>`).join('');
}
function selectPick(id, key) {
  const category = categories.find(c => c.key === key);
  if (category && ballot[key].length >= category.capacity && !ballot[key].includes(id)) {
    $('ballot-errors').textContent = `The ${category.title} group is full. Remove a team first.`;
    renderTable(); return;
  }
  for (const c of categories) ballot[c.key] = ballot[c.key].filter(teamId => teamId !== id);
  if (category) ballot[key].push(id);
  renderBallot(); renderTable(); save();
}
function renderMapSelects() {
  if (!event) return;
  const count = Number($('best-of').value);
  $('map-selects').innerHTML = Array.from({ length:count }, (_,i) => `<label for="map-${i}">Map ${i+1}<select id="map-${i}">${event.maps.map((map,j) => `<option ${i===j ? 'selected' : ''} value="${esc(map)}">${esc(map)}</option>`).join('')}</select></label>`).join('');
  $('map-selects').hidden = !$('manual-maps').checked;
}
function renderMatchup() {
  if (!event) return;
  try {
    const a = $('team-a').value, b = $('team-b').value;
    if (a === b) { $('matchup-result').textContent = 'Choose two different teams to compare.'; return; }
    const settings = { bestOf:Number($('best-of').value), mapWeight:Number($('map-weight').value) };
    if ($('manual-maps').checked) {
      settings.maps = Array.from($('map-selects').querySelectorAll('select'), select => select.value);
      if (new Set(settings.maps).size !== settings.maps.length) { $('matchup-result').textContent = 'Choose a different map for each slot.'; return; }
    }
    const prediction = predictMatch(event,a,b,settings);
    const teamA = event.teams.find(team => team.id === a), teamB = event.teams.find(team => team.id === b);
    $('matchup-result').innerHTML = `<div class="matchup-sides"><div class="matchup-side"><span>${esc(teamA.name)}</span><strong>${percent(prediction.probability)}</strong></div><div class="matchup-side"><span>${esc(teamB.name)}</span><strong>${percent(1-prediction.probability)}</strong></div></div><div class="versus-bar"><i style="width:${prediction.probability*100}%"></i></div>${prediction.maps.map((map,i) => `<div class="map-probability"><span>${esc(map)}</span><span>${percent(prediction.mapProbabilities[i])} / ${percent(1-prediction.mapProbabilities[i])}</span></div>`).join('')}`;
  } catch (error) { $('matchup-result').textContent = error.message; }
}
function download(filename, data) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)], { type:'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url),1000);
}

$('simulate').addEventListener('click', runSimulation);
$('sort').addEventListener('change', renderTable);
$('team-rows').addEventListener('change', e => { if (e.target.matches('[data-team]')) selectPick(e.target.dataset.team,e.target.value); });
$('ballot-slots').addEventListener('click', e => { const button = e.target.closest('[data-remove]'); if (button) selectPick(button.dataset.remove,''); });
$('clear-picks').addEventListener('click', () => { ballot = {threeZero:[],ordinaryAdvance:[],zeroThree:[]}; renderTable();renderBallot();save(); });
$('fill-picks').addEventListener('click', () => {
  if (!result) return;
  const used = new Set();
  for (const key of ['threeZero','zeroThree','ordinaryAdvance']) {
    const category = categories.find(c => c.key === key);
    const field = key === 'ordinaryAdvance' && $('includes-perfect').checked ? 'advance' : key;
    ballot[key] = result.teams.toSorted((a,b) => b[field]-a[field] || a.id.localeCompare(b.id)).filter(team => !used.has(team.id)).slice(0,category.capacity).map(team => {used.add(team.id);return team.id;});
  }
  renderTable();renderBallot();save();
});
$('export-picks').addEventListener('click', () => download('pickem-ballot.json', {
  exportedAt:new Date().toISOString(), prototypeVersion:'0.1.0', event, ballot,
  simulation:appliedOptions || null,
  scoring:{ threshold:Number($('threshold').value), ordinaryIncludesPerfect:$('includes-perfect').checked },
  note:'Research prototype. Ratings are supplied, not trained. Picks are not submitted to the game.'
}));
$('includes-perfect').addEventListener('change', () => {renderBallot();save();});
$('threshold').addEventListener('change', () => {renderScore();save();});
$('map-weight').addEventListener('input', () => {
  $('map-weight-label').textContent = `${Math.round(Number($('map-weight').value)*100)}%`;
  renderMatchup();
  if (result) status('Map weight changed. Run the simulation again to update stage probabilities and ballot scores.');
});
for (const id of ['runs','seed']) $(id).addEventListener('change', () => { if (result) status('Simulation settings changed. Run again to apply them.'); });
for (const id of ['team-a','team-b']) $(id).addEventListener('change', renderMatchup);
$('best-of').addEventListener('change', () => {renderMapSelects();renderMatchup();});
$('manual-maps').addEventListener('change', () => { $('map-selects').hidden = !$('manual-maps').checked;renderMatchup(); });
$('map-selects').addEventListener('change', renderMatchup);
$('import-file').addEventListener('change', async e => {
  const file = e.target.files[0]; if (!file) return;
  try {
    if (file.size > 1_000_000) throw Error('Use a stage JSON file smaller than 1 MB.');
    const parsed = JSON.parse(await file.text());
    // A ballot export contains its original event snapshot too.
    installEvent(parsed.event || parsed);
  } catch (error) { status(`Import rejected: ${error.message}`,true); }
  e.target.value = '';
});
async function loadDemo() {
  const response = await fetch(new URL('./data/demo.json',import.meta.url), {cache:'no-store'});
  if (!response.ok) throw Error(`Could not load example data (${response.status}).`);
  return response.json();
}
$('reset-demo').addEventListener('click', async () => {try {installEvent(await loadDemo());} catch (error) {status(error.message,true);} });
try {
  if (saved?.options) {
    if ([1000,10000,40000].includes(saved.options.runs)) $('runs').value = saved.options.runs;
    if (Number.isInteger(saved.options.seed) && saved.options.seed >= 0 && saved.options.seed <= 4294967295) $('seed').value = saved.options.seed;
    if (saved.options.mapWeight >= 0 && saved.options.mapWeight <= 1) $('map-weight').value = saved.options.mapWeight;
    $('map-weight-label').textContent = `${Math.round(Number($('map-weight').value)*100)}%`;
  }
  if (saved?.event) {
    try {
      validateEvent(saved.event);
      ballot = saved.ballot || ballot;
      if (Number.isInteger(saved.threshold) && saved.threshold>=5 && saved.threshold<=10) $('threshold').value = saved.threshold;
      $('includes-perfect').checked = Boolean(saved.ordinaryIncludesPerfect);
      installEvent(saved.event,true);
    } catch { installEvent(await loadDemo()); }
  } else installEvent(await loadDemo());
} catch (error) {status(`${error.message} Start the local web server with npm start.`,true);}
