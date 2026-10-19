#!/usr/bin/env python3
"""集中配置管理模块

管理所有硬编码的配置值，支持百万字级别小说的创作流程。
所有配置可通过环境变量覆盖。
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple


@dataclass
class QualityConfig:
    """质量检查配置"""
    
    # AI短语黑名单（去AI化检查）
    ai_phrase_blacklist: List[str] = field(default_factory=lambda: [
        "不禁", "仿佛", "映入眼帘", "心中暗道", "宛如",
        "似乎", "好像", "可能", "大概", "也许",
        "不由得", "不禁感到", "内心深处", "默默地",
    ])
    
    # 占位章检测参数
    max_stub_effective_chars: int = 800
    stub_marker: str = "<!-- NOVEL_FLOW_STUB -->"
    beat_sheet_stub_marker: str = "<!-- BEAT_SHEET_STUB -->"

    # 正文元信息污染标记（命中即判死，无豁免开关，只可用项目白名单）
    # 清单来源：references/editorial-team-protocol.md 的 P0 检测触发器。
    # 每项为 (正则, 分类, 修复提示)。
    body_meta_markers: List[Tuple[str, str, str]] = field(default_factory=lambda: [
        (r"<!--\s*(?:NOVEL_FLOW_STUB|BEAT_SHEET_STUB)\s*-->", "占位草稿标记",
         "章节仍是骨架占位，需补全正文"),
        (r"(?m)^\[[^\]\n]{1,24}\]\s*$", "方括号元信息块",
         "删除 [写作约束]/[相关历史剧情]/[本章目标]/[待写] 等非小说文本"),
        (r"（注[：:]|\(注[：:]|【(?:写作说明|待补充|作者按|作者注)】|\bTODO\b|\bFIXME\b"
         r"|PLACEHOLDER|待填充|扩写指令", "注记标记",
         "删除写作注记、TODO、待补充等元信息"),
        (r"本章禁止揭露|本章必须保留|不要在本章解决|本章推进范围"
         r"|当前是第\s*\d+\s*章（共|进度\s*\d+(?:\.\d+)?%", "约束 prompt 泄漏",
         "删除写前约束原文，正文只能是小说文本"),
        (r"\{\s*'(?:ok|command)'\s*:|anchor_file|\.py['\"]"
         r"|(?:00_memory|02_knowledge_base|03_manuscript|04_editing)[/\\]", "代码/路径残留",
         "删除脚本输出、JSON 片段与文件路径残留"),
        (r"补充推进\s*\d*\s*[：:]|叙述补偿[：:]", "写作指令残留",
         "删除「补写一段…」这类写作指令，正文只能是小说的叙述与对白"),
    ])

    # 占位人名候选：需配合触发条件（同词≥3次，或出现在对话标签位），不做字面判死
    placeholder_names: List[str] = field(default_factory=lambda: [
        "主角", "配角", "同伴", "路人甲", "角色A", "角色B", "某某", "待定",
    ])
    
    # 质量下限检查
    min_chars: int = 1200
    min_paragraphs: int = 6
    min_dialogue_ratio: float = 0.03
    
    # 发布判定关键词
    publish_keywords: List[str] = field(default_factory=lambda: [
        "可发布", "通过", "PASS", "审核通过", "质量合格"
    ])
    
    @classmethod
    def from_env(cls) -> "QualityConfig":
        """从环境变量加载配置"""
        config = cls()
        
        if "QUALITY_MIN_CHARS" in os.environ:
            config.min_chars = int(os.environ["QUALITY_MIN_CHARS"])
        
        if "QUALITY_MIN_PARAGRAPHS" in os.environ:
            config.min_paragraphs = int(os.environ["QUALITY_MIN_PARAGRAPHS"])
            
        if "QUALITY_MIN_DIALOGUE_RATIO" in os.environ:
            config.min_dialogue_ratio = float(os.environ["QUALITY_MIN_DIALOGUE_RATIO"])
        
        return config


@dataclass
class RetrievalConfig:
    """RAG检索配置"""
    
    # 停用词表
    stopwords: Set[str] = field(default_factory=lambda: {
        "我们", "你们", "他们", "她们", "它们", "这个", "那个", "一种", "已经", "因为", "所以", "如果",
        "但是", "然后", "自己", "不是", "不会", "就是", "还是", "一个", "一些", "可以", "时候", "什么",
        "怎么", "这样", "那样", "起来", "进去", "出来", "一下", "一样", "以及", "并且", "或者", "然后",
        "这里", "那里", "这些", "那些", "这样", "那样", "如此", "非常", "十分", "相当", "真的",
    })
    
    # 检索触发关键词
    trigger_keywords: Set[str] = field(default_factory=lambda: {
        "冲突", "反转", "伏笔", "回收", "真相", "背叛", "联盟", "新角色", "时间线", "回忆",
        "穿越", "死亡", "复活", "势力", "升级", "突破", "决战", "危机", "转折", "悬念",
        "揭露", "身份", "秘密", "阴谋", "复仇", "救赎", "牺牲", "传承", "觉醒", "封印",
    })
    
    # 轻场景关键词（用于跳过检索）
    light_scene_keywords: Set[str] = field(default_factory=lambda: {
        "日常", "过渡", "环境描写", "吃饭", "赶路", "休整", "闲聊", "铺垫",
        "修炼", "冥想", "休息", "准备", "整理", "收拾", "散步", "观光",
    })
    
    # 检索参数
    candidate_k: int = 12  # 粗筛候选数
    top_k: int = 4  # 精排返回数
    passage_max_chars: int = 220  # 片段最大字符数
    passages_per_chapter: int = 2  # 每章提取片段数
    
    # 缓存配置
    cache_max_entries: int = 200
    cache_ttl_seconds: int = 3600  # 1小时过期
    
    @classmethod
    def from_env(cls) -> "RetrievalConfig":
        """从环境变量加载配置"""
        config = cls()
        
        if "RETRIEVAL_CANDIDATE_K" in os.environ:
            config.candidate_k = int(os.environ["RETRIEVAL_CANDIDATE_K"])
        
        if "RETRIEVAL_TOP_K" in os.environ:
            config.top_k = int(os.environ["RETRIEVAL_TOP_K"])
        
        if "RETRIEVAL_CACHE_TTL" in os.environ:
            config.cache_ttl_seconds = int(os.environ["RETRIEVAL_CACHE_TTL"])
        
        return config


@dataclass
class FlowConfig:
    """流程执行配置"""
    
    # 执行锁配置
    lock_timeout_seconds: int = 300  # 5分钟超时
    lock_check_interval: float = 0.5  # 检查间隔
    
    # 快照配置
    snapshot_max_count: int = 10  # 最大保留快照数
    
    # 重试配置
    max_auto_retry_rounds: int = 2
    retry_delay_seconds: float = 1.0
    
    # 门禁配置
    gate_artifacts_min_bytes: int = 20
    
    # 存储路径（相对于项目根目录）
    memory_dir: str = "00_memory"
    manuscript_dir: str = "03_manuscript"
    knowledge_base_dir: str = "02_knowledge_base"
    gate_artifacts_dir: str = "04_editing/gate_artifacts"
    retrieval_dir: str = "00_memory/retrieval"
    flow_dir: str = ".flow"
    
    @classmethod
    def from_env(cls) -> "FlowConfig":
        """从环境变量加载配置"""
        config = cls()
        
        if "FLOW_LOCK_TIMEOUT" in os.environ:
            config.lock_timeout_seconds = int(os.environ["FLOW_LOCK_TIMEOUT"])
        
        if "FLOW_MAX_RETRY" in os.environ:
            config.max_auto_retry_rounds = int(os.environ["FLOW_MAX_RETRY"])
        
        return config


# =============================================================================
# 全局配置实例
# =============================================================================

# 懒加载的单例模式
_quality_config: Optional[QualityConfig] = None
_retrieval_config: Optional[RetrievalConfig] = None
_flow_config: Optional[FlowConfig] = None


def get_quality_config() -> QualityConfig:
    """获取质量配置（懒加载）"""
    global _quality_config
    if _quality_config is None:
        _quality_config = QualityConfig.from_env()
    return _quality_config


def get_retrieval_config() -> RetrievalConfig:
    """获取检索配置（懒加载）"""
    global _retrieval_config
    if _retrieval_config is None:
        _retrieval_config = RetrievalConfig.from_env()
    return _retrieval_config


def get_flow_config() -> FlowConfig:
    """获取流程配置（懒加载）"""
    global _flow_config
    if _flow_config is None:
        _flow_config = FlowConfig.from_env()
    return _flow_config


# =============================================================================
# 版本信息
# =============================================================================

__version__ = "8.0.0"
__all__ = [
    "QualityConfig",
    "RetrievalConfig", 
    "FlowConfig",
    "get_quality_config",
    "get_retrieval_config",
    "get_flow_config",
]
