# CS2 Pick’Em Lab

A beginner-friendly starting point for a GitHub-hosted CS2 Major prediction project. Compare teams, experiment with map strength, simulate a Swiss stage, and assess a set of Pick’Em choices.

[Open the website](https://yunjie0413.github.io/cs2-pickem-lab/) · [Source repository](https://github.com/yunjie0413/cs2-pickem-lab)

**This first version uses fictional teams and invented ratings.** It is a working single-stage prototype, not a trained model or a source of real tournament predictions. Automatic team and result updates are a later step.

## Run it locally

Install [Node.js 20 or newer](https://nodejs.org/). Open a terminal in this project folder, then run:

```sh
npm start
```

Open the local address printed by the server. No `npm install` is needed: this project has no external dependencies.

On Windows PowerShell, use `npm.cmd start` and `npm.cmd test` if PowerShell blocks the `npm` script.

To check the simulation engine:

```sh
npm test
```

## Try the prototype

1. Run the supplied fictional 16-team stage and inspect each team’s estimated finish probabilities.
2. Compare two teams and their map probabilities. Change the model settings to see how assumptions change the result.
3. Select a sample ballot: two teams to finish 3–0, six ordinary advancement picks, and two teams to finish 0–3. Evaluate that ballot against the simulated stages.
4. Import a modified tournament JSON file to try your own teams or completed rounds. Export your picks and settings to keep your experiment.

The **2/6/2 ballot is a sample layout**, not a claim about the current event’s official Pick’Em rules. The setting controlling whether ordinary advancement picks also count at 3–0 must match the rules of the event you intend to use.

## How the first model works

The match model blends general Elo-style team strength with a map-specific rating. For map weight `w`:

```text
R(team, map) = (1 - w) * overallRating + w * mapRating
P(A wins map) = 1 / (1 + 10^((R(B, map) - R(A, map)) / 400))
```

This is a replaceable baseline, not the final formula. The initial higher-seeded team always acts as Team A in the example veto: each team bans its weakest remaining maps and picks its strongest against the opponent. Real teams may choose their veto position differently. The series calculation assumes independent map outcomes conditional on the supplied ratings.

These are inspectable assumptions, not learned veto behavior. The invented map ratings are not historical map win rates. A real model should learn from dated results, account for opponents and roster changes, and reduce the influence of maps with little data.

The simulator repeatedly plays the remaining stage using those probabilities. Completed results stay fixed. Its job is to translate match probabilities into probabilities of finishes such as 3–0, 3–1, 3–2, or elimination, then score the ballot in each simulated outcome.

The probability of getting enough picks correct is a different objective from choosing each team’s most likely finish. Team outcomes interact through the bracket; a later ballot optimizer should evaluate complete ballots together.

## Import tournament data

Copy and edit `data/demo.json` to preserve the exact field shapes. The importer expects schema version 1:

| Field | Meaning |
| --- | --- |
| `schemaVersion` | `1` |
| `name` | Name of the dataset or tournament |
| `dataMode` | `demo` for fictional data or `manual` for a manually prepared dataset |
| `updatedAt` | Timestamp describing when the dataset was prepared |
| `source` | Human-readable data source or provenance |
| `stage` | Object with `name`, `allBestOfThree`, and `ordinaryIncludesPerfect` |
| `maps` | The stage’s seven-map pool |
| `teams` | Exactly 16 teams, each with `id`, `name`, `seed`, `rating`, and `mapRatings` |
| `completedRounds` | Array of completed rounds; each round is an array of match objects |

Each completed match has the form:

```json
{ "a": "team-id-a", "b": "team-id-b", "winner": "team-id-a" }
```

Use team IDs consistently, unique seeds from 1 through 16, and the same map keys as the map pool. Import **whole completed rounds**, with every match in that round recorded; partial live rounds are outside this prototype’s scope. Keep `completedRounds` empty for a stage that has not begun.

Overall and map ratings must be finite numbers from 0 to 4000, with a rating for every map. Completed matches must match the simulator’s seeded pairings. For a first experiment, start with equal map ratings matching each team’s overall rating; add map differences only when you have evidence for them.

Importing a manual dataset does not train the model. You are supplying its team and map ratings yourself. Do not label guessed ratings or incomplete results as live data.

## Publish your own copy on GitHub Pages

This project includes a GitHub Pages workflow. The source repository is `yunjie0413/cs2-pickem-lab`; these instructions also apply to a new copy or fork under your own account.

1. Create an empty repository on GitHub.
2. Upload this project’s files, keeping their directory structure. Include the hidden `.github/workflows` directory and its `deploy-pages.yml` workflow. If your upload tool hides dot-directories, use Git or GitHub Desktop so the workflow is included.
3. In the repository, open **Settings → Pages** and choose **GitHub Actions** as the build and deployment source.
4. Open **Actions** and run or inspect the Pages deployment workflow. After a successful deployment, open the website link shown by GitHub.

The GitHub repository stores your source code. GitHub Pages serves the website at a separate address, typically `https://YOUR-USERNAME.github.io/YOUR-REPOSITORY/`. Add that address to the repository’s Website field so you can open it from your GitHub project.

See [GitHub’s custom Pages workflow guide](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) if the repository or organization has additional Pages restrictions.

## A practical route to real predictions

| Step | Deliverable |
| --- | --- |
| 0 — This prototype | Fictional single-stage simulation, team comparison, manual imports, ballot scoring, and GitHub Pages deployment files |
| 1 — Real manual data | One verified event snapshot with its teams, seeds, map pool, completed rounds, and clearly documented rating assumptions |
| 2 — Automatic updates | A permitted data-provider adapter fetched by GitHub Actions; API credentials stored in repository secrets |
| 3 — Trained probabilities | Chronological Elo/map training, recency weighting, small-sample shrinkage, and calibration checked on future matches |
| 4 — Rules parity | Tests against the selected event’s actual pairings, seeding, vetoes, match formats, and Pick’Em scoring |
| 5 — Whole Major | Carry advancing teams and seeds into later stages, then simulate playoffs |
| 6 — Better ballots | Optimize the probability of meeting the required score; assess chosen ballots on fresh simulation samples |

Choose the data source before building a scraper. A simple adapter means the rest of the project can stay the same if you change providers.

| Data option | What to investigate |
| --- | --- |
| Manual JSON/CSV | Easiest free starting point; record where every result and rating came from |
| [PandaScore](https://developers.pandascore.co/docs/plan-reference) | Free fixtures and results versus paid detailed game data; verify tournament coverage and permission for this prediction use |
| [Liquipedia API](https://liquipedia.net/api) | Educational access eligibility, attribution, caching, API limits, and approval requirements |
| [GRID](https://grid.gg/plans/) | Access agreement, event coverage, historical map data, and availability for a hobby project |

[PandaScore’s browser FAQ](https://developers.pandascore.co/docs/frequently-asked-questions) says requests must run server-side. Its [terms](https://www.pandascore.co/terms-and-condition) also restrict odds-related uses, so confirm that your planned Pick’Em probability tool is permitted. [Liquipedia’s terms](https://liquipedia.net/api-terms-of-use) require API access rather than automated HTML scraping. Do not publish provider credentials or raw datasets unless their license permits it.

GitHub Pages is static hosting. A scheduled Action can fetch permitted data, validate it, and rebuild the site without putting an API key in the browser. This is suitable for periodic updates; scheduled workflows are not a guaranteed real-time feed.

## Simulation precision is not prediction accuracy

For one estimated probability near 50%, 1,000 independent simulations give an approximate pointwise 95% Monte Carlo margin of **±3.1 percentage points**. With 10,000, that is **±0.98 points**. These estimates describe random sampling noise conditional on the model, not whether its predictions are correct.

More runs make a wrong model more precise. Before relying on real forecasts, compare chronological held-out match predictions with simple baselines using calibration, Brier score, or log loss. Keep future results out of earlier training data. A convergence rule should have a minimum run count, a stated precision target, and a maximum run count; small changes between two batches alone are not evidence of accuracy.

The prototype uses fixed run budgets rather than an adaptive convergence claim. Its probability-based auto-fill uses the same simulation sample it displays, so the displayed ballot score is exploratory. A future optimizer should select on one sample and report performance on a fresh independent sample.

## Rules to verify before using a real Major

Use the [Valve Major supplemental rulebook](https://github.com/ValveSoftware/counter-strike_rules_and_regs/blob/main/major-supplemental-rulebook.md) and the selected organizer’s event rules. Swiss pairings depend on record, opponent difficulty, initial seed, and rematch avoidance. Event formats can differ from general documentation: [PGL’s Singapore 2026 page](https://www.pglesports.com/cs2/pgl-major-singapore-2026/) lists a best-of-three Stage 3 and best-of-five final.

This prototype models one stage. Treat event format, map veto behavior, exact Pick’Em categories, and scoring as inputs that need explicit verification before presenting real recommendations.

