"""跨层领域模型（Domain Models）：所有 Pydantic 字段定义。

字段名与 PRD §5、§6 一一对应（snake_case）。
按 `02-代码架构与目录约定.md` §2.5 组织。M0 阶段为空占位；
M1+ 加入：
- enums.py     §5.4 LifecyclePhase / §6.6.1 TurnWriter / §6.7.1 HintStatus 等
- ids.py       §5.2 ScenarioId / NpcCharacterId / TurnId 类型别名
- package.py / intake.py / framework.py / roster.py / narrative.py / mission.py
- turn.py / hint.py / analytics.py / job.py
"""
