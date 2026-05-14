"""数据仓库层（③ Repository）：data/ JSON 文件读写。

按 `02-代码架构与目录约定.md` §2.3 组织。M0 阶段为空占位；
M1+ 逐步加入：
- base.py            通用 JSON 读写工具、按包加锁
- package_repo.py    package.json
- intake_repo.py / analysis_repo.py / framework_repo.py / roster_repo.py
- narrative_repo.py / mission_repo.py / turn_repo.py / hint_repo.py / analytics_repo.py
- job_repo.py        jobs/{job_id}.json
"""
