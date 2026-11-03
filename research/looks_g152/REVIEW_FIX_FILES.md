# 精确改动文件清单

引擎移植仅涉及以下唯一文件，完整差异见 review_fix/engine-change.diff：

`firmware/engine_v60_g152/candidate/containers/product/src/firmware/engine/core/eng_core.c`

以下包含测试、构建、队列、报告和包清单。运行回执、日志及最终 DAT/ELF 由 SHA256SUMS 逐项列出，本表不展开这些生成物。

| 路径 | 类型 | SHA256 |
|---|---|---|
| `firmware/engine_v60_g152/candidate/containers/product/src/firmware/engine/core/eng_core.c` | 修改 | `c62ca5337493c3ce974a30e8e7ca4b8bc68d593a0b965d1600dcc0fdeee7482d` |
| `firmware/package_v38_g152/MANIFEST.json` | 修改 | `70be42d77a225d86431c448399673a03d2b7c78e5e1a3ef574855cf6c4ef9f8e` |
| `firmware/package_v38_g152_test/MANIFEST.json` | 修改 | `19b05c20706705b5e03f409cc48f99b406074af33d65baaa0784d4f836f12b09` |
| `research/looks_g152/CANDIDATE_HISTORY.json` | 修改 | `524b9f3c4a60eda61c6b7e9c89c2453bd3291acd96d0117aefe8dc4b7b81f835` |
| `research/looks_g152/CORE_REGRESSION_SCOPE.md` | 修改 | `c693cdedcf23d06805f98dc889f65d9da770e068c23074c45494123ed3880a1b` |
| `research/looks_g152/FINAL_GAPS.json` | 修改 | `7fc4d451cdb845d29652a21528de6f5ebad610748202ec027362ec5f0855149e` |
| `research/looks_g152/PROGRESS.md` | 修改 | `1d372a0593fd69497b16b999d905575cd0665c5ef2761fafe92e7dca017b6152` |
| `research/looks_g152/REGRESSION_SCOPE.md` | 修改 | `486d792987b6a2097607ac24b1717b11c74095fea2a50ee2f3a179313f83c2fb` |
| `research/looks_g152/REPORT.md` | 修改 | `848cb537872a8de1c2e6ca80b5f401aad6065f86444620a50c4a6ad853c5d205` |
| `research/looks_g152/REVIEW_FIX_SCOPE.md` | 新增 | `d9e5ec267658ff8960ea87935a2c59a90eb82442bcb0f5fddf8ad6c5e2050fe2` |
| `research/looks_g152/SNAPSHOT.md` | 修改 | `cd6eafd919d24c851371e76c107f4551c37a6f3e6517a83b5d70484de822bc13` |
| `research/looks_g152/acceptance.json` | 修改 | `e05a2a3650b5a8269a5d16394e3e675a62036e5c3a799de4a54b93f35bf5d460` |
| `research/looks_g152/cleanup.json` | 修改 | `20a9851546ae5611da5ee8f01db7d8a7cf1607259a611f350fe3b09255d06744` |
| `research/looks_g152/final_audit.py` | 修改 | `778ed5fbabb73051edb93ded97c1c4a1dff8f21ce05bf40d9f87c3d409f404fd` |
| `research/looks_g152/finish.py` | 修改 | `372da4b36e4976ee0fbf43719c3d3d6ff7f783a7f2b93544a1141d6de3f79881` |
| `research/looks_g152/fix_handoff.py` | 新增 | `e5355b9c8ff87b089c5085613e3b9ddd45f2a9866d1c128e175a4caf670beaa2` |
| `research/looks_g152/format_checks.py` | 修改 | `427ba663085a9c6c999f074e3fc97bb956625c1d60353c9694787f5d280806e4` |
| `research/looks_g152/package.json` | 修改 | `069a30b2097eaeed27e302920c3c7941788e6fce61160bd3854e185d72103114` |
| `research/looks_g152/queue-fix-final.json` | 新增 | `e5b27176d1d577bb3c2e15bf1bb81a46916f208e2c3e21d1650722c4d7170a7f` |
| `research/looks_g152/queue-fix-math.json` | 新增 | `84786cc19fe4466eff8b1d513db20b1d2dbd807faa2fe90a6a0ffa5b18855e08` |
| `research/looks_g152/queue-fix-matrix.json` | 新增 | `e5cba7f740ae3b6f4cf6cd3641bf3aa20148102313869a99f7e6696b3cc448a3` |
| `research/looks_g152/queue-fix-native.json` | 新增 | `66766fa51f3bed8dd2dca618afca7fd68539441b3ec735a18c8cb285ca526925` |
| `research/looks_g152/queue-fix-observed.json` | 新增 | `086612e3c016308409c1470382e66fd220471dda1679bda609dd20075f5e7195` |
| `research/looks_g152/queue-fix-required.json` | 新增 | `0c6b610d00015cb19317142283ba982737397c8ed3cc6e7ac1c4b572436c7b53` |
| `research/looks_g152/queue-fix-retry.json` | 新增 | `488e5b4ed45ca802250a48a7653a1247b1b6b7b7d00da0ba96791f689ec4842f` |
| `research/looks_g152/queue-fix-smoke.json` | 新增 | `b3fda09c57009b5b5966658477f0b59f513c7a9d46fbe51b6b2635f40dac80c5` |
| `research/looks_g152/queue-required.json` | 修改 | `0c6b610d00015cb19317142283ba982737397c8ed3cc6e7ac1c4b572436c7b53` |
| `research/looks_g152/rebuild_review_fix.py` | 新增 | `e0cbc83451fdb60dd1a4e5e2bac3609f9652cbe0add3aa48936221859b41d878` |
| `research/looks_g152/regression_scope.json` | 修改 | `d076b5306c45fc36d35b394d896b50f582ffce0d5c3c3d11d22836d8f1bb2734` |
| `research/looks_g152/report.py` | 修改 | `0a733440175281404b15ac993d825febb7283243bde1b2a95fea61436a459a29` |
| `research/looks_g152/resume.json` | 修改 | `a6e297cbc834c9fb7094917b53cd0c9749d20528bc145e4a50f26d2b787030dd` |
| `research/looks_g152/review_fix/RUNS.md` | 新增 | `a7d4821bc2b570d2652c4ac4f26a46a51afdd9e85ef33145876bf49f19521b14` |
| `research/looks_g152/review_fix/build.json` | 新增 | `3c51514f866a37252b45d720feab5958591313ba06ed33d1fd4d09e3d87e491e` |
| `research/looks_g152/review_fix/deferred_rechecks.json` | 新增 | `e8c9e65f5aeb4d08b0d327f59e8f9cacc38c95731bfed89f9d3ce79cdea18fde` |
| `research/looks_g152/review_fix/engine-change.diff` | 新增 | `103401855656490e6a26a36671664a241fc74dae6802cfbe50cf9e2609eefe53` |
| `research/looks_g152/review_fix/fixture_revision.json` | 新增 | `41ca4cfb471c9d145f13bb300cd4dadfa49827a1b50592adccc46166d3d11926` |
| `research/looks_g152/review_fix/start.json` | 新增 | `b2ada55f463895cfaa4255e959021558e8987ef1babaf0bc964108164597bb3a` |
| `research/looks_g152/review_fix_audit.py` | 新增 | `952da06dbfe00d273138168aeb3a1f2459e341b70049a0919d8322fe2caf9dc8` |
| `research/looks_g152/review_fix_checks.py` | 新增 | `83ec4f56ccd77ac5581382246c24daf8fbf85215fbb85e30a7fdf34f97f2a60c` |
| `research/looks_g152/review_fix_finish.py` | 新增 | `09daedaea5c07a73818c881e3140f40a7c1c59377bbb8dd28cd627b1cf1e4651` |
| `research/looks_g152/review_fix_photo.py` | 新增 | `1cdb1a80ebafd65de580d991168e36ff86fd1a611d38c7922c588fe6d27db730` |
| `research/looks_g152/review_fix_photo_v3.py` | 新增 | `22f6b60d144401db6b8b928d124d923934003d4c3878d90718e6ec4cd89eac25` |
| `research/looks_g152/review_fix_report.py` | 新增 | `937213337ae9eb43d890eb1546fbd573ed5dd3f6ec0af5b4c4e083c0a4b993a9` |
| `research/looks_g152/seal.py` | 修改 | `dca20782d3fb2c4f5acc0f3e7172e5f0ae5ba2848b8367b98ba4c877161299e1` |
| `research/looks_g152/service-proof.json` | 修改 | `7ebb705fb782a6e052953fe8d0d997c87db664cca859186a43b439782884e632` |
| `research/looks_g152/unverified_checks.py` | 修改 | `63d1de8539a3be2cf303c780992fe39fc7421ed537f0451163956c19ee5e99a9` |
