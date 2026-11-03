# g138 review work state

The main scheduler is PID 82302, exec session 15803. It has exactly two execution slots, no global deadline and 10,800-second per-job limits. It is running queue.json (81 matrix groups, user-tool, plus a deliberately stopped partial new-feature suite). Do not start another testing process while both slots run. Tests and prechecks are serial in each slot. No subagents, no git writes, no card access. All review outputs are under this directory. TMP root is /Volumes/Workspace/Scratch/tmp/projectricoh/review-g138 and must be removed at the end.

Initial protected hashes: evidence/inputs-before.json (18,016 files). OS write/network fence passed evidence/scope-check.json. Canonical product inputs must remain unchanged. The initial old wrapper reset TMP into the review folder; later wrappers force compiler/runner environments into the requested Scratch root. The first safety case is therefore included in repair-queue.json for a final repeat.

Confirmed observations (evidence/focused-review.json, final DAT):
- Synthetic startup with complete recipe-5 unit rows, T=2, S mode 4, WB9/9: first H01 rejects restoration and retains the mixed input, no applied mark and no W.
- Selecting 04 Default through normal DISP keys then sets S mode to1 but issues ZERO unit W and retains all recipe-5 rows, despite internal committed stock state. P1 candidate; native boot reachability of the starting state is NOT proven. Source eng_core.c 158, 195-205, 595-596, 640-674.
- Unknown nonzero 40-byte S tail is preserved on first open, but ordinary recipe5 selection replaces it with a valid record. Violates persist_recipe_r2 section7.1 read-only rule. P1 candidate. Source services.c 314-333 and eng_core.c 370-371.

Already independently passed: artifact_check.py => artifact-results.json, only DAT differs among30 package files, main108060 B / margin64. es/list_check.py => es/list-results.json (144177 windows,56756 moves,4054 frames,226 fillers,2814 endpoint cases,1153416 adapter group moves). borrow_math.py => evidence/borrow-math.json,3430 points and6860 comparisons against separately built g137 engine, all552B outputs identical, no equal adjacent outputs. Other controls at defaults, not Cartesian products.

Supplemental persist_check all50mm was deliberately stopped at PID82514 after6 completed PASS cases (cold-none,restore,restore-matches-select,restore-once,bad-crc,bad-magic), to prioritize the explicitly requested full81. evidence/persist-selected-stop.json records it, receipt persist-50mm returns -15. Do not call that whole suite PASS. More focused checks are queued as prechecks.

Review-tool errors kept in raw receipts:
- focused_review originally inspected UI before DAT loading; fixed summary to omit UI until image_base exists. Rerun succeeded, not a product fault.
- static_integrity wrongly assumed all data segments unchanged; relocation/directory/record offsets differ. Fixed it to require unchanged sections4,6,7. It has not yet rerun.
- precheck assertions initially prevented matrix groups locked,cutpoints,exits from running. Hook now records nonzero prechecks and continues. The 5 repaired main jobs (including50mm transitions and safety) are in repair-queue.json, run AFTER main scheduler finishes (or serialize within a free slot).
- Current-g137 separator/cycle contract was incompletely ported in inherited tests. transitions50mm failed line68 because first pad is --------, not blank. Copied wrapper now maps line68/card row7, line81/empty entries row2, line96/error row1, and line82/empty-entry DOWN wraps to0. locked_cases.py line115 now admits separator alongside reason and blank, preserving all reason/lock assertions. Raw locked-final4/8 failures were exactly this separator, not product failure. Further repeats must use the new wrapper.

Future prechecks in prechecks.json: static_integrity.py, lock_trace.py (8 model service boundary cases with actual S-store tracing), record-busy, selected persist inel-row/inel-raw/value-ends, transitions-final (older supplementary name), raw exits-final. Prechecks may be missed if their job was already running when mapping was edited; inspect OS receipts/logs. Do not assume they ran. lock_trace.py and static_integrity.py are untested yet.

Next work:
1. Keep main81 running; inspect failures and adapt only genuinely stale expectations. Preserve original receipts. Continue updates while waiting on exec session; do not use sleep polling.
2. Add current-contract label replacement, since old label groups assume3 rows and old default navigation. Current HC BW display controls are [1,2,3,4,9] (no Amount). Expected card: title,C/H,S/F,G0,Default,separator,blank,blank; items:title,Cont,High,Shad,Fade,Filt,separator,blank. Std card count6,Defaultrow5. Old project groups refer to retired uv_levels; boundary_sweep.py copied to this directory targets g138 and must be run (precheck group124-50mm-project). Preserve raw original group failures and link current coverage explicitly.
3. Confirm static/source package binding and reference lock bytes match current body, heap improvement64 B (inherited three-leak remaining53096 <77336, risk stillopen).
4. Finish81, run repair-queue. Build complete REGRESSIONS.md/JSON with outer receipts AND inner results, exact final DAT and user-fixture hashes. Distinguish tool failures, old contract failures, PASS, not started.
5. Write Chinese REVIEW.md first line exactly 不能上卡 or 可以上卡. Likely no-go due aboveP1. Cover8 requested topics, inherited g137 problem table (P1-01,P2-03,g124/P2-01,P2-04,g129/P2-01,g135P2s,listP2,etc). Actual REPORT section6 has9 items, grade first5 and address rest. Busy retries are6 compensations, source time.time is host wall time, not camera latency. ! unsaved warning is P2 opaque; suggest text such as6 NoSave in existing row. Three photos can be kept with extra no-photo checks of items/card endpoints, exact Cont+1 afterrestore, user title both pages, user entry reboot04 and one-shot restore.
6. Verify all frozen inputs unchanged, archive/log/manifest, cleanup ONLY own Scratch. No product/report edits.

Skills used: unslop, human-voice (pr_code_review pack and gpt note), technical-writing. Memory used registryMEMORY.md20-24 and rollout_summaries/2026-10-29T23-23-35-n67l-projectricoh_gen135_independent_review_no_go.md12-17 for proof/fence lessons. Final answer must append exactly one memory citation block (thread id01a189f9-dba6-7922-b7d0-be2d344aabd7). Do not cite memory in the actual review report.

## Later updates

- Scope changed to separate later supplemental checks from main matrix groups. Future prechecks now retain ONLY group124-50mm-labels (labels_current50 and persist users50). Older planned mappings are archived in evidence/prechecks-planned-r1.json. Do not assume old mappings ran.
- Main users50 passed, and its actual precheck restore_compare50 passed: all4096 S bytes,9 rows (503 owned bytes), T and displayed state identical to normal keys. Evidence/restore-compare-50mm.json.
- Main values50 passed full7/7 with OS exit0. Main view-reentry50 passed. Main project50 failed retired uv_levels as expected; boundary-sweep.json current host-C replacement passed18484 rejects with unchanged output,3469 accepted requests and18 invalid slots.
- Main reentry-six50 had a rebuild PRECHECK failure only, output relocated but archive.relative_to(c.HERE) metadata still assumed product root. rebuild_review.py now maps artifact-relative metadata, sha and linker archive paths into review/local/rebuild. New version not run yet; ensure no link uses original archive.
- supplemental-queue.json has14 direct checks (static integrity, actual lock-store trace, fixed rebuild, restorecompare28/mount, recordbusy50, targetmath3units, labels28/mount, empty3units). Run AFTER main and repair queues with2slots. Then audit-queue.json must run AFTER all writers finish.
- target_math_review.py generates a fresh private host-model H01 state, validates frozen r2 reference vector multiset against current table points, and reuses original target_check.py. It runs actual decoded M32R instructions translated to C for all1133+1134+1163=3430 points and about15 original-interpreter samples perunit. Label host-driven compute, NOT cold boot/RTOS or native menu acceptance. Script is untested.
- audit_communications.py imports original g122 auditor directly to avoid ARG_MAX, groups all complete legacy RPC streams by their exact DAT/fixture hashes. It must run last; no file can be concurrently rewritten. Script is untested.
- Fresh primary tests now have corrected g137 separator expectations. Original raw reports and early tool-blocked receipts remain. repair-queue.json still requires5 final jobs after main.
- Potential third contract finding: persist_recipe_r2 section7.2(2) requires actual ordinary-mode evidence; g138 checks S fields, epochs, rows/T only, not MY/boot origin. REPORT section6(5) admits old records can survive MY/reset/source events when values coincide. Decide severity explicitly against literal normal-boot requirement; do not imply a physical MY reproduction was run.
- New local disassembly has current inherited P2 cut offsets: preview preparation0xD794, previewcall0xD798, IRQrestore0xD790. ui_list native redraw call0xC2CC. Oldg137 offsets must not be reused.

## Current checkpoint at matrix28mm values/view-reentry

- Main session15803/PID82302 remains active, two slots. Last finishes: exits28 and transitions28 both exit0; transitions42 cases passed after separator/empty-loop ports. Main first50 values full7/7 passed. No product code/report edits.
- REVIEW.md now exists as a RUNNING draft generated by make_report.py from REVIEW.in.md and current REGRESSIONS. Finalize only after all matrix,5 repair jobs,16 supplementals and audit finish. make_report.py --final requires queue completion/all extra receipts0 and final REGRESSIONS.
- Supplemental queue now16 jobs; includes held_lock_review.py (7 op2 attempts, zero actual S stores expected) and partial_baseline_review.py (one nonstock row, otherwise normal eligible S; 04Default should incorrectly accept zeroW, record04 and show>4, even afterOK; script notrun yet).
- Important confirmed artifact finding: exact published DAT88a4359b has ZERO user entries (GXUI+24), g137also0. User fixture3ccb0f3a has32. Original third photo cannot be done with the exact published DAT. P2 acceptance-plan issue added; do not propose putting the unapproved fixture on a card. Formal fixed candidate must contain a user entry and be sealed/reviewed at its own newSHA.
- Current labels50 replacement passed actual M32R. persist_check users50 passed575.6s, both user-card/items names and user-record clearing/reboot04. Both in group124-50mm-labels prechecks. Its raw obsolete label group will still return1 at line12 (STALE_LABEL_CONTRACT), normal.
- No current target_math, lock_trace, held_lock, partial_baseline, static_integrity, fixed rebuild, empty3unit runs yet; all in later explicit supplemental queue. Most old planned prechecks were missed or deliberately removed; never count them.
- Generated make_repeat_queue.py produces fresh81 job directories for clean reruns without deleting previous proof; main user-tool fixture is reused and still identity-checked. Scheduler now checks volume identity on every NEW run. Existing process loaded prior schedulercode but volume was validated before it began.
- seal.py must run under offline.sb after REGRESSIONS is final and all4 queues completed, hashes18016 original inputs, acquires scheduler lock, deletes ONLY owned Scratch/review-g138 and writes evidence/seal.json. Then render finalreport and generate/check SHA256SUMS excluding itself/local derivedbinaries.
- make_tables.py understands main + repairs. It does not convert retired uv_levels/oldlabels into rawPASS. Expected final outcomes about69PASS+6STALE_RETIRED_FUNCTION+6STALE_LABEL_CONTRACT, with current hostC range and M32R label replacements separate. Do not assume that count until observed.
- New own helperfiles: make_report.py, REVIEW.in.md, REVIEW.md draft, WRAPPER.md, static_integrity.py, partial_baseline_review.py, held_lock_review.py, target_math_review.py, audit_communications.py, seal.py. All untested helpers must run before final.

## Checkpoint at Mount exits/transitions

- Main session15803/PID82302 still owns both test slots. Active Mount exits started19:20:08 UTC, transitions19:22:42 UTC. 28mm values1594.9s, users610.3s, reentry-six1219.2s, half158.3s all exit0. Old28mm project/labels exit1 classified as retired function / old label contract. Mount safety366.6s, locked313.5s, nested433.3s, cutpoints244.8s all passed.
- Supplemental queue now17 items. New excluded_bw_review.py supplies saved HC BW+Cont1 S/record and stock unit rows as explicit model inputs, expecting excluded firstADJ to preserve S3 without completing saved recipe or canonical04. This is NOT a native power-cycle replay and is untested until the supplemental queue runs. Final template has a required EXCLUDED_BW_RESULT substitution.
- g138_host.accept_module now isolates decoder cache by REVIEW_JOB under local/models. This prevents direct supplemental jobs on the same unit from racing cache listings. Existing running main jobs keep their original isolated wrapper directories.
- Scheduler now creates the specified TMP root only after the volume UUID/APFS/writable gate, so clean reruns after seal recreate Scratch correctly. Existing main loaded earlier scheduler code; initial mount gate was already checked.
- REVIEW.in.md now names exact parameter-lock addresses and native init/take/release entrypoints. Rebuild helper docstring accurately describes review-local output relocation. No product or implementation report writes.

## Correction to the proposed HC BW startup case

Static final-DAT input inspection shows slot3 HC BW native mode is1 (Standard), neutral WB. The proposed mode3 premise was false, caught before test execution. excluded_bw_review.py and its queue job/template substitution were removed; supplemental queue is back to16. evidence/excluded-bw-preparation.json records this preparation result. Do NOT restore or count that unexecuted case. P1-01 still rests on the successful Setting1/recipe5 and unknown-ledger observations plus pending one-row partial-baseline case.

## Latest checkpoint: second matrix, 50mm exits/transitions

- Main session15803, schedulerPID82302. Active group126-50mm-exits PID62871 started20:25:15 UTC and group126-50mm-transitions PID64188 started20:27:32 UTC. First39 slots finished; three early matrix groups had no inner execution and await the 5-job repair queue. Complete matrix groups now40, before the latest make_tables refresh.
- First-family Mount values1608.5s, view-reentry711.8s, reentry-six1223.6s, users612.7s, half158.6s passed. Mount oldproject/oldlabels exited1 as retired API / old label contract. Second-family50 safety375.5s, locked315.9s, nested434.0s, cutpoints244.3s all passed. No timeout.
- make_tables.py now verifies each receipt's raw-log SHA and requires full values7 / transitions42 child exits for PASS. Actual first-family7/42 counts were checked. It still preserves all stale raw exits and original early attempts.
- g138_host.setup now verifies APFS UUID/writable state before creating outputs and TMP. Its decoder cache remains per REVIEW_JOB. These future helper changes only affect review code; no product/report edits.
- New static issue g138/P2-04: services.c280/312 read S length/extension before IRQ;321-322 do not recheck these fields inside. r2 section6.1 explicitly requires recheck. Native reachability is unknown; do NOT claim observed overflow. No extra test was added for this.
- Report template clarifies host-driven H01/key entry, matrix host CRC, per-Engine restore_done, conditional heap size comparison, and photo1's Cont0 -> verified reboot -> Cont+1 sequence to avoid stale-record false passes. All final helper evidence remains pending until main81 and repair finish, then16 supplemental jobs, then audit.

## Latest checkpoint: second matrix 50mm values/view-reentry

- Same main session15803 / PID82302. group126-50mm-exits passed952.6s and transitions passed868.4s. Active values PID72118 since20:41:08 UTC and view-reentry PID72414 since20:42:01 UTC. Completed matrix groups42, plus3 still TOOL_NOT_EXECUTED until repair. No timeout. Do not add a third test process.
- findings-queue.json is an OPTIONAL rerun entry for focused_review, partial_baseline, held_lock. Do NOT run it as an extra required phase now: its scripts are already proven or in the16-job supplemental queue. It exists for future user reproduction with the same10800s/two-slot/fence controls. Only four required execution queues remain main,repair,supplemental,audit.
- New manifest.py writes/checks a complete inventory of ALL review files including local raw evidence and derived binaries. It rejects symlinks and Python cache files and acquires the scheduler lock. Run only after all tests, seal and final report/WORK_STATE writes are done: manifest.py --write, then --check. Do not edit anything in this review after writing the manifest unless regenerating it. The report now includes these final commands.
- Static preparation confirmed the one-row P1 fixture is viable: default reference recipes4 and5 differ on rows0,1,2,3,7,8. This was only input inspection, NOT the pending M32R partial-baseline execution. HC BW premise remains withdrawn (mode1), no such supplemental job.

## Latest checkpoint: second matrix 28mm values/view-reentry

- Main is still session15803/PID82302 with exactly two active tests. group126-28mm-values PID13604 started21:50:29 UTC; view-reentry PID14463 started21:51:26 UTC. Last new passes: other-users50 537.3s, safety28 371.9s, locked28 310.0s, nested28 434.4s, cutpoints28 243.9s, transitions28 871.3s, exits28 944.7s. Completed groups56 plus3 early nonexecuted pending repair. Current draft/REGRESSIONS may lag; regenerate from receipts before final.
- Rebuild helper now rejects any .a/.o argument still naming canonical engine55/candidate/local, records linked_inputs, and checks the newly rebuilt ELF .engine bytes against the rebuilt DAT. Fixed helper still untested until supplemental queue. Inspect actual link logs after it runs; do not infer independence only from subprocess0.
- static_integrity.py now regenerates local/source-diff.txt and compares source hunks against the supplied source-diff.txt, ignoring only diff headers/timestamps/absolute root prefixes. This new check has not run yet. If mismatch, inspect evidence and actual input drift; do not alter product or author report.
- target_math_review.py now also checks 505-byte applied signatures (all9 owned rows503B plusT2B) across adjacent selectable levels. It verifies current M32R-derived output against frozen full552B reference first. A FAIL_APPLIED_NEIGHBORS is a potential real no-effect point finding, not automatically a wrapper error; investigate it and do not remove the check to get PASS. This is within the same3 target-math jobs, supplemental total remains16. make_report expects the new projection fields.
- Photo instructions now explicitly target50mm first and say WB compensation9/9. Current source has3 g138 P1s plus4 g138 P2s; inherited issues remain separately listed. Firstline stays不能上卡. No source/report/package writes.

## Main matrix draining its final job

- Main session15803/PID82302 still running. Sole active test is group126-mount-other-users PID62123 since23:36:06 UTC. All other main jobs have exited. Complete groups77; after this final job main complete count should be78 because3 early prechecks prevented inner execution. Do not call it81 before repair.
- Latest Mount passes: safety359.6s, locked305.8s, nested425.9s, cutpoints237.8s, transitions849.3s, exits941.9s, values1568.8s, view-reentry704.4s, reentry-six1183.6s, users601.1s, half154.4s. Old project and labels exited1 as expected stale contracts. No timeout.
- Once main completes, start repair-queue.json with2slots using the same scheduler. After5 repair jobs, run supplemental-queue.json (16jobs), then audit-queue.json (1slot). Do not overlap schedulers or bypass their lock merely to fill the idle tail slot. Optional findings-queue is only a user rerun entry, not an extra required phase.
- All supplemental helpers remain unexecuted, including newly extended static source-diff binding, rebuilt-ELF/archive guards, applied505B adjacency check, lock-store trace, and one-row baseline witness. Existing50mm restore comparison, labels, user persistence, borrowed6860 comparisons and focused defects are already successful as noted above.
- Final workflow: make_tables.py --final; inspect supplemental/audit evidence and current source findings; sandboxed seal.py (hash18016 inputs and remove ownedTMP); make_report.py --final; write final WORK_STATE before manifest; manifest.py --write then --check; no further review-file changes. Check no own test processes remain. Only then final Chinese verdict/report links/memory citation.

## Repair queue running

- Main session15803 completed exit0 at23:44:27 UTC. Main82 jobs excluding user prerequisite:65 exit0,12 stale matrix exits1,3 precheck-blocked groups,1 old transitions failure,1 deliberately stopped feature suite. make_tables confirms78 complete /81,65PASS+6retired+6oldlabels+1unclassified plus3notexecuted.
- Repair scheduler now PID66075, exec session52501, started23:44:41 UTC. Active safety50-final-r2 PID66089 and locked50-final-r2 PID66090, two slots. Wait on52501, NOT old15803. Then cutpoints/exits/transitions as queued. This queue must finish all5 before supplemental16 starts.

## Supplemental queue active

Repair session52501 finished5/5 at00:08:03 UTC. REGRESSIONS --final is81 complete,69PASS+6retired+6oldlabels. Supplemental schedulerPID77207, session60900 started00:08:20 UTC with16jobs. static-integrity-final failed because our diff comparison omitted resident/abi.h; candidate hunks820lines matched, provided diff has21 ABI lines. Script now compares both scopes. Queue file renames this job static-integrity-final-r2, but the running scheduler already loaded the original queue and will finish with the old failure. AFTER it completes, archive supplemental-queue-complete.json to supplemental-queue-complete-r1.json, resume updated supplemental queue to run only r2 and preserve all original receipts. rebuild-final PASSED in5.17s; check evidence/rebuild.json linked_inputs/code binding. Active lock-trace-final and partial-baseline-final at this checkpoint. Do not run another test while both slots active.

## Supplemental math identity adaptation

- Restore comparisons now50/28/Mount allPASS; locktrace8/8PASS and record-busyPASS. held-lock and target-math active in original16-job queue.
- target-math50 original failed before compute because retained g135 locator assumes only relocation mutates the image. Actual g138 RAM identity differs solely at t_seen RVA62584/4B (-1 initializer ->2 after H01), all relocation checks pass. Original RAM/state/log retained. Wrapper now verifies ELF symbol+size, every relocation and exact four-byte difference, normalizes only an identity COPY, then calls retained strict locator; execution RAM unchanged. New job workdirs include jobname. Disk queue math3 names now-r2; after original scheduler completes, archive complete-r1 and resume currentqueue static-r2 plusmath3-r2.
- Existing28 job loaded original script and may fail similarly; Mount may loadfixedscript. Preserve every original receipt. No product changes.

## Supplemental retry active

- Original16 supplemental jobs completed at00:40:02 UTC:12exit0, staticdiff scope +math3identity preparation exits1 preserved in supplemental-queue-complete-r1.json. All3currentlabels, all3empty, all3restorecomparison,8locktraces,recordbusy,heldlock,partialbaseline,rebuild arePASS/OBSERVED asappropriate.
- Current schedulerPID96688, execsession16156, started00:40:13 UTC, currentdiskqueue skips12successreceipts and runs static-r2 plusmath3-r2. static-integrity-final-r2 alreadyexit0; validatescandidate+residentabi diff,34sources19headers,codebinding,lockreference,zero publishedusers32fixtureusers,108060Bmain. Active50/28targetmath-r2; Mount waits.
- Corrected mathidentity adapter obtains ELF symbolsize using retained full ELFreader (cam.p.elf only mapsnames tovalues), masks onlyt_seen4B in strict identitycopy, runtimeRAM unchanged. Each newmath job hasseparateWORK name. Actualcompute results stillpending; do notcountbeforeevidence.
- Reportdraft regenerated with81finalmatrix butRUNNING supplementals. Make_report now includes rebuiltELFhash/final-linkaudit and heldlock3428RPC/1690unitW; restore bytecomparison scope explicitly5Cont+1.
- After thisqueue: inspect3mathresults/allzero, audit-queue1slot, make_tables --final, sandboxedseal, make_report --final, finalWORK_STATE, manifestwrite/check, no editsaftermanifest.

## Communication audit active

- Supplemental retry session16156 finished16/16exit0 at00:45:19 UTC. Math all3430points/45directnative samples passed, 505B applied neighboraliases0. Original4 preparationfailures remainarchived, notconvertedtooriginalPASS.
- Audit schedulerPID99637, execsession21339 started00:45:20 UTC, solecommunications-final processPID99661. Waiton21339, inspect rpc-summary plus perDAT groups. Then finaltables, sandboxedseal, finalreport, finalWORK_STATE, manifestwrite/check.

## Final delivery checkpoint

- UTC 2026-10-31T00:46:31.309115+00:00. REVIEW.md is FINAL, firstline exactly不能上卡. Three g138P1 findings and fourg138P2 findings are documented alongside inheriteditems; no productcode/report/package/body edits.
- Matrix81/81 executed:69PASS,6STALE_RETIRED_FUNCTION,6STALE_LABEL_CONTRACT, originalrawerrors andattempts retained. Current replacements reportedseparately, notpromoted tooriginalPASS.
- Final supplemental16/16exit0; all3restores S4096/rows503/T/L1 identical for5Cont+1; locktrace8/8; targetmath3430points+45direct samplesPASS, appliedneighboraliases0. Previous4preparationfailures remain in complete-r1/logs.
- RPCauditPASS forpublished88a4359b plusfixture3ccb0f3a,2478sourcefiles,114deduplicated fullstreams,3unitsperDAT PASS,no exclusions/missing/failures. Scope islegacy matrixdirectory, notallhelper summaries.
- seal.json checked18016initialfrozeninputs,0changes; ownedScratchreview-g138 removed. No remainingown testexecutor wasfound afteraudit. All8requestedreviewtopics,81rowtable, reruncommands and3photoplan are inreport.
- Complete SHA256inventory is generated after this finalentry and then checked. No reviewfile edits shouldfollow inventory creation.
