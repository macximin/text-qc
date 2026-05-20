# Novel QC Handoff 2026-05-20

Public-safe handoff for the manuscript QC harness work. Do not paste manuscript text,
private SSOT paths, or HWP/HWPX manuscript artifacts into this public repository or GitHub issues.

## Git State

- Repository: `macximin/text-qc`
- Branch: `main`
- Harness baseline commit before this handoff doc: `98be15b`
- Verification: `python -m pytest` passed locally on 2026-05-20.

To continue on another PC:

```powershell
git fetch origin
git checkout main
git pull --ff-only origin main
```

If the other PC has no clone yet:

```powershell
git clone https://github.com/macximin/text-qc.git
cd text-qc
```

Then run the fetch/checkout/pull sequence above. The command order is `git pull origin main`,
not `git pull main origin`.

## Private Artifacts

The manuscript and run artifacts are intentionally excluded by `.gitignore` because the remote is
public. Continue with the private handoff package in the internal archive. The private package
contains the original merged manuscript, policy SSOT, AA audit reports, edit logs, and a private
handoff README.

Do not commit these private artifact classes:

- `초기 원고(input)/*`
- `최종 원고(output)/*`
- `workspace/*`
- `*.hwp`, `*.hwpx`, `*.docx`, `*.pdf`, `*.zip`

## Current Harness Decisions

- `ⓐ` is for auto-approved surface corrections: spelling, spacing, punctuation, and obvious typo fixes.
- `ⓐⓐ` must use an actionable comparison form: `ⓐⓐ{source|candidate}[판단: reason]`.
- `ⓐⓐ` cannot contain only review memo text such as "needs canon decision"; it must show the actual
  candidate text, deletion, or insertion that would happen if approved.
- Consistency review includes contextual typos, contextual continuity, verisimilitude, numeric carryover,
  timeline, role/title drift, state regression, and non-reader-facing notes.
- Ethical judgment, reader-comfort smoothing, guilt insertion, donation insertion, and rescue-hero rewriting
  are excluded unless explicitly requested or already present in source text.
- For AI-generated or AI-suspected manuscript text, unmarked time reversals, scene splices, duplicated recaps,
  and state regressions are not protected as authorial intent by default.
- Once a canonical name is decided for the same person, company, or institution, aliases/initials/real-name
  variants are not automatically accepted. Use one canonical form unless a scene-specific abbreviation function
  is justified as an `ⓐⓐ` exception candidate.

## Next Workstreams

1. Restore or reference the private artifact package from the internal archive.
2. Apply the AA policy SSOT to manuscript edits as visible `ⓐ` and `ⓐⓐ` markers.
3. Keep simple surface fixes as `ⓐ`; keep policy, canon, continuity, deletion, and insertion choices as `ⓐⓐ`.
4. Fully compare duplicated chapters before deleting or suppressing any chapter-sized block.
5. After approval and application, generate source-vs-edited diff reports by purpose:
   spelling/surface, internal memo cleanup, canonical naming, timeline, numbers/accounts, roles, space/legal state,
   author-intent risk, and deletion/compression.
6. Re-run consistency review on the edited candidate to catch backpatch regressions.

## GitHub Issue Map

Keep issue content public-safe and avoid manuscript excerpts.

- [#10 Novel QC handoff: restore private artifacts and continue from main](https://github.com/macximin/text-qc/issues/10)
- [#11 Novel QC: apply AA policy SSOT with visible A/AA markers](https://github.com/macximin/text-qc/issues/11)
- [#12 Novel QC: canonical-name and alias pass](https://github.com/macximin/text-qc/issues/12)
- [#13 Novel QC: duplicate chapter and time-splice gates](https://github.com/macximin/text-qc/issues/13)
- [#14 Novel QC: source-vs-edited diff reports after approvals](https://github.com/macximin/text-qc/issues/14)
