import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { validateEvent, createRng, mapProbability, seriesProbability, predictMatch, initialState, pairRound, applyRound, simulateStage, scoreBallot } from './engine.mjs';

const fixture = JSON.parse(readFileSync(new URL('./data/demo.json', import.meta.url), 'utf8'));
const clone = value => structuredClone(value);
const close = (a, b, tolerance = 1e-12) => assert.ok(Math.abs(a - b) <= tolerance, `${a} != ${b}`);

test('ratings and series probabilities are complementary; equal teams give 50%', () => {
  const [a, b] = fixture.teams;
  for (const map of fixture.maps) {
    close(mapProbability(a, a, map), .5);
    close(mapProbability(a, b, map) + mapProbability(b, a, map), 1);
  }
  for (const p of [.05, .2, .5, .8, .95]) {
    close(seriesProbability([p]), p);
    close(seriesProbability([p, p, p]), 3 * p ** 2 - 2 * p ** 3);
    close(seriesProbability([p, .4, .7]) + seriesProbability([1-p, .6, .3]), 1);
  }
  assert.throws(() => seriesProbability([.2, .4]));
  assert.throws(() => mapProbability(a, b, fixture.maps[0], 2));
});

test('veto ordering is independent of caller order and map override is exact', () => {
  const [a, b] = fixture.teams;
  for (const bestOf of [1, 3]) {
    const ab = predictMatch(fixture, a.id, b.id, { bestOf });
    const ba = predictMatch(fixture, b.id, a.id, { bestOf });
    assert.deepEqual(ab.maps, ba.maps);
    close(ab.probability + ba.probability, 1);
    assert.equal(ab.maps.length, bestOf);
  }
  const maps = fixture.maps.slice(0, 3);
  const result = predictMatch(fixture, a.id, b.id, { bestOf: 3, maps });
  assert.deepEqual(result.maps, maps);
  close(result.probability, seriesProbability(maps.map(m => mapProbability(a, b, m))));
  assert.throws(() => predictMatch(fixture, a.id, a.id));
  assert.throws(() => predictMatch(fixture, a.id, b.id, { maps: ['Unknown'] }));
});

test('seeded RNG and full stage simulations are reproducible', () => {
  const x = createRng(42), y = createRng(42), z = createRng(43);
  const values = Array.from({ length: 20 }, () => x());
  assert.deepEqual(values, Array.from({ length: 20 }, () => y()));
  assert.notDeepEqual(values, Array.from({ length: 20 }, () => z()));
  assert.ok(values.every(n => n >= 0 && n < 1));
  const first = simulateStage(fixture, { runs: 120, seed: 123 });
  assert.deepEqual(first, simulateStage(fixture, { runs: 120, seed: 123 }));
  assert.notDeepEqual(first.outcomes, simulateStage(fixture, { runs: 120, seed: 124 }).outcomes);
});

test('every simulated stage has exactly eight advancers, two 3-0 and two 0-3', () => {
  const event = clone(fixture);
  event.stage.allBestOfThree = true;
  const result = simulateStage(event, { runs: 500, seed: 8 });
  for (const outcomes of result.outcomes) {
    assert.equal(outcomes.filter(x => x === 3).length, 2);
    assert.equal(outcomes.filter(x => x === 0).length, 2);
    assert.equal(outcomes.filter(x => x >= 2).length, 8);
    assert.equal(outcomes.filter(x => x === 2).length, 6);
  }
  close(result.teams.reduce((sum, t) => sum + t.advance, 0), 8);
  close(result.teams.reduce((sum, t) => sum + t.threeZero, 0), 2);
  close(result.teams.reduce((sum, t) => sum + t.zeroThree, 0), 2);
  assert.ok(result.standings.every(t => t.wins === 0 && t.losses === 0));
});

test('Swiss pairings follow initial 1v9 and preserve records without rematches', () => {
  const rng = createRng(2026);
  for (let run = 0; run < 120; run++) {
    const state = initialState(fixture);
    assert.deepEqual(pairRound(state, 1), Array.from({ length: 8 }, (_, i) => [fixture.teams[i].id, fixture.teams[i+8].id]));
    for (let round = 1; round <= 5; round++) {
      const pairs = pairRound(state, round);
      const seen = new Set();
      for (const [a, b] of pairs) {
        const ta = state.find(t => t.id === a), tb = state.find(t => t.id === b);
        assert.equal(ta.wins, tb.wins);
        assert.equal(ta.losses, tb.losses);
        assert.ok(!ta.opponents.includes(b));
        assert.ok(!seen.has(a) && !seen.has(b));
        seen.add(a); seen.add(b);
      }
      applyRound(state, pairs.map(([a, b]) => ({ a, b, winner: rng() < .5 ? a : b })));
    }
    assert.ok(state.every(t => t.wins === 3 || t.losses === 3));
  }
});

function completedEvent(rounds) {
  const event = clone(fixture), state = initialState(event);
  for (let round = 1; round <= rounds; round++) {
    const matches = pairRound(state, round).map(([a, b]) => ({ a, b, winner: event.teams.find(t => t.id === a).seed < event.teams.find(t => t.id === b).seed ? a : b }));
    event.completedRounds.push(matches);
    applyRound(state, matches);
  }
  return event;
}

test('completed rounds are validated and frozen, including finished stages', () => {
  const event = completedEvent(3);
  assert.equal(validateEvent(event), event);
  const result = simulateStage(event, { runs: 80 });
  const first = result.teams.find(t => t.id === event.teams[0].id);
  assert.equal(first.threeZero, 1);
  assert.deepEqual(result.standings.find(t => t.id === first.id), { id: first.id, wins: 3, losses: 0 });
  const final = simulateStage(completedEvent(5), { runs: 4 });
  assert.ok(final.outcomes.every(outcome => JSON.stringify(outcome) === JSON.stringify(final.outcomes[0])));
  assert.ok(final.teams.every(t => [0, 1].includes(t.advance)));
  const partial = completedEvent(1); partial.completedRounds[0].pop();
  assert.throws(() => validateEvent(partial), /all 8 matches/);
  const wrongPair = completedEvent(1); wrongPair.completedRounds[0][0].b = fixture.teams[9].id;
  assert.throws(() => validateEvent(wrongPair), /inconsistent/);
  const wrongWinner = completedEvent(1); wrongWinner.completedRounds[0][0].winner = 'unknown';
  assert.throws(() => validateEvent(wrongWinner), /winner/);
});

test('whole-ballot scoring uses exclusive buckets and rejects incomplete ballots', () => {
  const ids = fixture.teams.map(t => t.id);
  const result = { runs: 2, teams: ids.map(id => ({ id })), outcomes: [[3,3,2,2,2,2,2,2,0,0,1,1,1,1,1,1], [1,1,1,1,1,1,1,1,1,1,3,3,2,2,0,0]] };
  const ballot = { threeZero: ids.slice(0,2), ordinaryAdvance: ids.slice(2,8), zeroThree: ids.slice(8,10) };
  const score = scoreBallot(result, ballot);
  assert.equal(score.valid, true);
  close(score.expectedCorrect, 5);
  close(score.successProbability, .5);
  close(score.distribution[0], .5); close(score.distribution[10], .5);
  const incomplete = scoreBallot(result, { threeZero: [], ordinaryAdvance: [], zeroThree: [] });
  assert.equal(incomplete.valid, false); assert.equal(incomplete.successProbability, null);
  const duplicate = clone(ballot); duplicate.zeroThree[0] = duplicate.threeZero[0];
  assert.equal(scoreBallot(result, duplicate).valid, false);
  const mixed = { threeZero: [ids[1],ids[10]], ordinaryAdvance: [ids[0],...ids.slice(3,8)], zeroThree: ids.slice(8,10) };
  close(scoreBallot(result, mixed, { ordinaryIncludesPerfect: true }).expectedCorrect - scoreBallot(result, mixed).expectedCorrect, .5);
});

test('invalid input is rejected before simulation', () => {
  const event = clone(fixture); event.teams[0].seed = 2;
  assert.throws(() => validateEvent(event), /seeds must be unique/);
  const badMap = clone(fixture); delete badMap.teams[0].mapRatings.Mirage;
  assert.throws(() => validateEvent(badMap), /every map/);
  assert.throws(() => simulateStage(fixture, { runs: 0 }), /Runs/);
  assert.throws(() => simulateStage(fixture, { mapWeight: NaN }), /Map weight/);
});
