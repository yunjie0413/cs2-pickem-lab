// Deterministic, dependency-free baseline. Ratings are inputs, not fitted here.
const PAIRING_TABLE = [
  [[0,5],[1,4],[2,3]], [[0,5],[1,3],[2,4]],
  [[0,4],[1,5],[2,3]], [[0,4],[1,3],[2,5]],
  [[0,3],[1,5],[2,4]], [[0,3],[1,4],[2,5]],
  [[0,5],[1,2],[3,4]], [[0,4],[1,2],[3,5]],
  [[0,2],[1,5],[3,4]], [[0,2],[1,4],[3,5]],
  [[0,3],[1,2],[4,5]], [[0,2],[1,3],[4,5]],
  [[0,1],[2,5],[3,4]], [[0,1],[2,4],[3,5]],
  [[0,1],[2,3],[4,5]],
];

function requireThat(condition, message) {
  if (!condition) throw new Error(message);
}

export function createRng(seed = 42) {
  const value = String(seed);
  let state = 2166136261;
  for (let i = 0; i < value.length; i++) state = Math.imul(state ^ value.charCodeAt(i), 16777619);
  return () => {
    state = (state + 0x6D2B79F5) | 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function mapProbability(a, b, map, mapWeight = 0.5) {
  requireThat(Number.isFinite(mapWeight) && mapWeight >= 0 && mapWeight <= 1, 'Map weight must be between 0 and 1.');
  const ra = (1 - mapWeight) * a.rating + mapWeight * (a.mapRatings?.[map] ?? a.rating);
  const rb = (1 - mapWeight) * b.rating + mapWeight * (b.mapRatings?.[map] ?? b.rating);
  requireThat(Number.isFinite(ra) && Number.isFinite(rb), 'Team ratings must be finite numbers.');
  return 1 / (1 + 10 ** ((rb - ra) / 400));
}

export function seriesProbability(probabilities) {
  requireThat(Array.isArray(probabilities) && probabilities.length > 0 && probabilities.length % 2 === 1, 'Supply an odd number of map probabilities.');
  requireThat(probabilities.every(p => Number.isFinite(p) && p >= 0 && p <= 1), 'Map probabilities must be between 0 and 1.');
  // Probability of winning a majority; unplayed maps can be treated as latent draws.
  let count = [1];
  for (const p of probabilities) {
    const next = Array(count.length + 1).fill(0);
    count.forEach((mass, wins) => { next[wins] += mass * (1 - p); next[wins + 1] += mass * p; });
    count = next;
  }
  return count.slice((probabilities.length + 1) / 2).reduce((a, b) => a + b, 0);
}

function vetoMaps(event, a, b, bestOf, mapWeight) {
  const higher = a.seed < b.seed ? a : b;
  const lower = higher === a ? b : a;
  const pool = [...event.maps];
  const ordered = team => [...pool].sort((x, y) => {
    const opponent = team === higher ? lower : higher;
    return mapProbability(team, opponent, x, mapWeight) - mapProbability(team, opponent, y, mapWeight) || event.maps.indexOf(x) - event.maps.indexOf(y);
  });
  const ban = (team, n) => { for (let i = 0; i < n; i++) pool.splice(pool.indexOf(ordered(team)[0]), 1); };
  const pick = team => { const choice = ordered(team).at(-1); pool.splice(pool.indexOf(choice), 1); return choice; };
  if (bestOf === 1) { ban(higher, 2); ban(lower, 3); ban(higher, 1); return pool; }
  ban(higher, 1); ban(lower, 1);
  const first = pick(higher), second = pick(lower);
  ban(lower, 1); ban(higher, 1);
  return [first, second, pool[0]];
}

export function predictMatch(event, aId, bId, { mapWeight = 0.5, bestOf = 1, maps } = {}) {
  const a = event.teams.find(t => t.id === aId), b = event.teams.find(t => t.id === bId);
  requireThat(a && b && aId !== bId, 'Select two different teams from this event.');
  requireThat(bestOf === 1 || bestOf === 3, 'This Swiss-stage baseline supports BO1 and BO3.');
  const chosen = maps ?? vetoMaps(event, a, b, bestOf, mapWeight);
  requireThat(Array.isArray(chosen) && chosen.length === bestOf && new Set(chosen).size === chosen.length && chosen.every(m => event.maps.includes(m)), `Supply ${bestOf} different maps from this event.`);
  const mapProbabilities = chosen.map(map => mapProbability(a, b, map, mapWeight));
  return { probability: seriesProbability(mapProbabilities), maps: [...chosen], mapProbabilities };
}

export function initialState(event) {
  return event.teams.map(t => ({ id: t.id, seed: t.seed, wins: 0, losses: 0, opponents: [] }));
}

function highLowMatching(group) {
  if (!group.length) return [];
  const a = group[0];
  for (let j = group.length - 1; j >= 1; j--) {
    const b = group[j];
    if (a.opponents.includes(b.id)) continue;
    const rest = group.slice(1).filter(t => t !== b);
    const remaining = highLowMatching(rest);
    if (remaining) return [[a, b], ...remaining];
  }
  return null;
}

export function pairRound(state, round) {
  if (round === 1) {
    const sorted = [...state].sort((a, b) => a.seed - b.seed);
    return sorted.slice(0, 8).map((team, i) => [team.id, sorted[i + 8].id]);
  }
  const lookup = new Map(state.map(t => [t.id, t]));
  const buchholz = t => t.opponents.reduce((total, id) => { const o = lookup.get(id); return total + o.wins - o.losses; }, 0);
  const active = state.filter(t => t.wins < 3 && t.losses < 3);
  const records = [...new Set(active.map(t => `${t.wins}-${t.losses}`))].sort((a, b) => Number(b.split('-')[0]) - Number(a.split('-')[0]));
  const pairs = [];
  for (const record of records) {
    const group = active.filter(t => `${t.wins}-${t.losses}` === record).sort((a, b) => buchholz(b) - buchholz(a) || a.seed - b.seed);
    let matched;
    if (round >= 4) {
      requireThat(group.length === 6, 'Unexpected Swiss record group size.');
      const row = PAIRING_TABLE.find(option => option.every(([a, b]) => !group[a].opponents.includes(group[b].id)));
      requireThat(row, 'No rematch-free pairing available.');
      matched = row.map(([a, b]) => [group[a], group[b]]);
    } else matched = highLowMatching(group);
    requireThat(matched, 'No rematch-free pairing available.');
    pairs.push(...matched.map(([a, b]) => [a.id, b.id]));
  }
  return pairs;
}

export function applyRound(state, matches) {
  const lookup = new Map(state.map(t => [t.id, t]));
  for (const { a, b, winner } of matches) {
    const ta = lookup.get(a), tb = lookup.get(b);
    const loser = winner === a ? tb : ta;
    lookup.get(winner).wins++;
    loser.losses++;
    ta.opponents.push(b); tb.opponents.push(a);
  }
  return state;
}

export function validateEvent(event) {
  requireThat(event && event.schemaVersion === 1, 'Expected event schemaVersion 1.');
  requireThat(typeof event.name === 'string' && event.name.trim(), 'Event name is required.');
  requireThat(['demo', 'manual'].includes(event.dataMode), 'dataMode must be demo or manual.');
  requireThat(typeof event.updatedAt === 'string' && Number.isFinite(Date.parse(event.updatedAt)), 'updatedAt must be a date string.');
  requireThat(typeof event.source === 'string' && event.source.trim(), 'Data source description is required.');
  requireThat(event.stage && typeof event.stage.name === 'string' && typeof event.stage.allBestOfThree === 'boolean' && typeof event.stage.ordinaryIncludesPerfect === 'boolean', 'Stage must include its name and boolean format/scoring settings.');
  requireThat(Array.isArray(event.maps) && event.maps.length === 7 && new Set(event.maps).size === 7 && event.maps.every(m => typeof m === 'string' && m.trim()), 'Provide seven unique map names.');
  requireThat(Array.isArray(event.teams) && event.teams.length === 16, 'A Swiss stage needs exactly 16 teams.');
  requireThat(new Set(event.teams.map(t => t.id)).size === 16, 'Team IDs must be unique.');
  requireThat(new Set(event.teams.map(t => t.seed)).size === 16, 'Team seeds must be unique.');
  for (const t of event.teams) {
    requireThat(typeof t.id === 'string' && t.id.trim() && typeof t.name === 'string' && t.name.trim(), 'Every team needs a nonempty ID and name.');
    requireThat(Number.isInteger(t.seed) && t.seed >= 1 && t.seed <= 16, 'Seeds must be integers 1–16.');
    requireThat(Number.isFinite(t.rating) && t.rating >= 0 && t.rating <= 4000, `Invalid overall rating for ${t.id}.`);
    requireThat(t.mapRatings && event.maps.every(m => Number.isFinite(t.mapRatings[m]) && t.mapRatings[m] >= 0 && t.mapRatings[m] <= 4000), `Supply ratings from 0 to 4000 on every map for ${t.id}.`);
  }
  requireThat(Array.isArray(event.completedRounds) && event.completedRounds.length <= 5, 'completedRounds must contain zero to five complete rounds.');
  const state = initialState(event);
  for (let r = 0; r < event.completedRounds.length; r++) {
    const expected = pairRound(state, r + 1);
    const matches = event.completedRounds[r];
    requireThat(Array.isArray(matches) && matches.length === expected.length, `Completed round ${r + 1} must include all ${expected.length} matches.`);
    const key = (a, b) => JSON.stringify([a, b].sort());
    const expectedKeys = new Set(expected.map(([a, b]) => key(a, b)));
    const seen = new Set();
    for (const match of matches) {
      requireThat(match && expectedKeys.has(key(match.a, match.b)), `Completed round ${r + 1} contains a match inconsistent with the seeded Swiss pairings.`);
      const k = key(match.a, match.b);
      requireThat(!seen.has(k), `Completed round ${r + 1} contains a duplicate match.`);
      requireThat(match.winner === match.a || match.winner === match.b, 'Each completed match winner must be one of its two teams.');
      seen.add(k);
    }
    applyRound(state, matches);
  }
  return event;
}

export function simulateStage(event, { runs = 10000, seed = 42, mapWeight = 0.5 } = {}) {
  validateEvent(event);
  requireThat(Number.isInteger(runs) && runs >= 1 && runs <= 100000, 'Runs must be an integer between 1 and 100,000.');
  requireThat(Number.isFinite(mapWeight) && mapWeight >= 0 && mapWeight <= 1, 'Map weight must be between 0 and 1.');
  const rng = createRng(seed), frozen = initialState(event);
  event.completedRounds.forEach(round => applyRound(frozen, round));
  const standings = frozen.map(({ id, wins, losses }) => ({ id, wins, losses }));
  const teams = event.teams.map(({ id }) => ({ id, threeZero: 0, advance: 0, ordinaryAdvance: 0, zeroThree: 0 }));
  const outcomes = [];
  const predictions = new Map();
  const probabilityFor = (a, b, bestOf) => {
    const key = JSON.stringify([a, b, bestOf]);
    if (!predictions.has(key)) predictions.set(key, predictMatch(event, a, b, { bestOf, mapWeight }).probability);
    return predictions.get(key);
  };
  for (let run = 0; run < runs; run++) {
    const state = frozen.map(t => ({ ...t, opponents: [...t.opponents] }));
    const lookup = new Map(state.map(t => [t.id, t]));
    for (let round = event.completedRounds.length + 1; round <= 5; round++) {
      const matches = pairRound(state, round).map(([a, b]) => {
        const ta = lookup.get(a);
        const bestOf = event.stage.allBestOfThree || ta.wins === 2 || ta.losses === 2 ? 3 : 1;
        return { a, b, winner: rng() < probabilityFor(a, b, bestOf) ? a : b };
      });
      applyRound(state, matches);
    }
    const outcome = state.map((t, i) => {
      if (t.wins === 3) {
        teams[i].advance++;
        if (t.losses === 0) { teams[i].threeZero++; return 3; }
        teams[i].ordinaryAdvance++; return 2;
      }
      if (t.wins === 0) { teams[i].zeroThree++; return 0; }
      return 1;
    });
    outcomes.push(outcome);
  }
  for (const team of teams) for (const field of ['threeZero', 'advance', 'ordinaryAdvance', 'zeroThree']) team[field] /= runs;
  return { runs, seed, teams, outcomes, standings };
}

export function scoreBallot(result, ballot, { threshold = 5, ordinaryIncludesPerfect = false } = {}) {
  const errors = [], specs = [['threeZero', 2], ['ordinaryAdvance', 6], ['zeroThree', 2]];
  const ids = new Map(result.teams.map((t, i) => [t.id, i]));
  const chosen = [];
  for (const [field, count] of specs) {
    const items = ballot?.[field];
    if (!Array.isArray(items) || items.length !== count) errors.push(`Choose exactly ${count} teams for ${field}.`);
    if (Array.isArray(items)) for (const id of items) { chosen.push(id); if (!ids.has(id)) errors.push(`Unknown team: ${String(id)}.`); }
  }
  if (new Set(chosen).size !== chosen.length) errors.push('A team can occupy only one ballot slot.');
  if (!Number.isInteger(threshold) || threshold < 0 || threshold > 10) errors.push('Threshold must be an integer from 0 to 10.');
  if (errors.length) return { valid: false, errors, successProbability: null, expectedCorrect: null, distribution: [] };
  const distribution = Array(11).fill(0);
  for (const outcome of result.outcomes) {
    let correct = 0;
    for (const id of ballot.threeZero) if (outcome[ids.get(id)] === 3) correct++;
    for (const id of ballot.ordinaryAdvance) if (outcome[ids.get(id)] === 2 || ordinaryIncludesPerfect && outcome[ids.get(id)] === 3) correct++;
    for (const id of ballot.zeroThree) if (outcome[ids.get(id)] === 0) correct++;
    distribution[correct]++;
  }
  for (let i = 0; i < distribution.length; i++) distribution[i] /= result.runs;
  return { valid: true, errors: [], successProbability: distribution.slice(threshold).reduce((a,b) => a+b,0), expectedCorrect: distribution.reduce((sum,p,i) => sum+p*i,0), distribution };
}
