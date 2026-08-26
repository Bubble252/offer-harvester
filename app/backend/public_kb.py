"""Public admissions knowledge-base records and local workspace storage.

The public KB is deliberately separate from private student facts.  It stores
source metadata, structured admissions facts, and chunks that can be indexed by
the existing RAG pipeline.  It never treats an embedding as the source of
truth.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Type

from models import new_id, now_iso
from pydantic import BaseModel, Field

PublicRecordKind = Literal[
    "university",
    "college",
    "program",
    "advisor",
    "policy",
    "deadline",
    "faq",
]

AuthorityLevel = Literal[
    "university_official",
    "graduate_school_official",
    "college_official",
    "advisor_official",
    "admissions_platform",
    "manual_summary",
    "unofficial",
    "unknown",
]

AuditStatus = Literal["pending", "passed", "needs_review", "failed"]


class PublicKBSource(BaseModel):
    source_id: str = Field(default_factory=lambda: new_id("pubsrc"))
    source_kind: str = "public_web"
    title: str = ""
    url: str = ""
    publisher: str = ""
    authority_level: AuthorityLevel = "unknown"
    published_at: str = ""
    fetched_at: str = Field(default_factory=now_iso)
    valid_for_year: Optional[int] = None
    content_hash: str = ""
    robots_status: str = "unknown"
    tos_status: str = "unknown"
    privacy_scope: Literal["public"] = "public"
    audit_status: AuditStatus = "pending"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PublicKBRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: new_id("pubrec"))
    record_kind: PublicRecordKind
    university_id: str = ""
    college_id: str = ""
    name: str = ""
    aliases: List[str] = Field(default_factory=list)
    summary: str = ""
    structured_facts: Dict[str, Any] = Field(default_factory=dict)
    source_refs: List[str] = Field(default_factory=list)
    valid_for_year: Optional[int] = None
    status: Literal["candidate", "active", "superseded", "archived"] = "candidate"
    audit_status: AuditStatus = "pending"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class PublicKBChunk(BaseModel):
    chunk_id: str = Field(default_factory=lambda: new_id("pubchunk"))
    record_id: str
    source_id: str
    title: str = ""
    text: str
    url: str = ""
    content_hash: str = ""
    valid_for_year: Optional[int] = None
    authority_level: AuthorityLevel = "unknown"
    audit_status: AuditStatus = "pending"
    embedding_route: Literal["local", "external_public", "none"] = "none"
    embedding_model: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PublicKBManifest(BaseModel):
    schema_version: str = "public-kb.v1"
    name: str = "PublicAdmissionsKnowledgeBase"
    scope: Literal["public_only"] = "public_only"
    target_groups: List[str] = Field(
        default_factory=lambda: ["all_985", "strong_211", "specialized_strong_universities"]
    )
    universities: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


PUBLIC_KB_TARGET_UNIVERSITIES: List[Dict[str, Any]] = [
    {
        "university_id": "pku",
        "name": "北京大学",
        "aliases": ["Peking University", "PKU"],
        "groups": ["985", "c9"],
    },
    {
        "university_id": "tsinghua",
        "name": "清华大学",
        "aliases": ["Tsinghua University", "THU"],
        "groups": ["985", "c9"],
    },
    {
        "university_id": "ruc",
        "name": "中国人民大学",
        "aliases": ["Renmin University of China", "RUC"],
        "groups": ["985"],
    },
    {
        "university_id": "buaa",
        "name": "北京航空航天大学",
        "aliases": ["Beihang University", "BUAA"],
        "groups": ["985"],
    },
    {"university_id": "bit", "name": "北京理工大学", "aliases": ["BIT"], "groups": ["985"]},
    {"university_id": "bnu", "name": "北京师范大学", "aliases": ["BNU"], "groups": ["985"]},
    {"university_id": "cau", "name": "中国农业大学", "aliases": ["CAU"], "groups": ["985"]},
    {"university_id": "muc", "name": "中央民族大学", "aliases": ["MUC"], "groups": ["985"]},
    {
        "university_id": "nankai",
        "name": "南开大学",
        "aliases": ["Nankai University"],
        "groups": ["985"],
    },
    {
        "university_id": "tju",
        "name": "天津大学",
        "aliases": ["Tianjin University", "TJU"],
        "groups": ["985"],
    },
    {
        "university_id": "dlut",
        "name": "大连理工大学",
        "aliases": ["DUT", "DLUT"],
        "groups": ["985"],
    },
    {
        "university_id": "neu",
        "name": "东北大学",
        "aliases": ["Northeastern University"],
        "groups": ["985"],
    },
    {
        "university_id": "jlu",
        "name": "吉林大学",
        "aliases": ["Jilin University", "JLU"],
        "groups": ["985"],
    },
    {"university_id": "hit", "name": "哈尔滨工业大学", "aliases": ["HIT"], "groups": ["985", "c9"]},
    {
        "university_id": "fudan",
        "name": "复旦大学",
        "aliases": ["Fudan University"],
        "groups": ["985", "c9"],
    },
    {"university_id": "sjtu", "name": "上海交通大学", "aliases": ["SJTU"], "groups": ["985", "c9"]},
    {
        "university_id": "tongji",
        "name": "同济大学",
        "aliases": ["Tongji University"],
        "groups": ["985"],
    },
    {"university_id": "ecnu", "name": "华东师范大学", "aliases": ["ECNU"], "groups": ["985"]},
    {
        "university_id": "nju",
        "name": "南京大学",
        "aliases": ["Nanjing University", "NJU"],
        "groups": ["985", "c9"],
    },
    {
        "university_id": "seu",
        "name": "东南大学",
        "aliases": ["Southeast University", "SEU"],
        "groups": ["985"],
    },
    {
        "university_id": "zju",
        "name": "浙江大学",
        "aliases": ["Zhejiang University", "ZJU"],
        "groups": ["985", "c9"],
    },
    {
        "university_id": "ustc",
        "name": "中国科学技术大学",
        "aliases": ["USTC"],
        "groups": ["985", "c9"],
    },
    {
        "university_id": "xmu",
        "name": "厦门大学",
        "aliases": ["Xiamen University", "XMU"],
        "groups": ["985"],
    },
    {
        "university_id": "sdu",
        "name": "山东大学",
        "aliases": ["Shandong University", "SDU"],
        "groups": ["985"],
    },
    {"university_id": "ouc", "name": "中国海洋大学", "aliases": ["OUC"], "groups": ["985"]},
    {
        "university_id": "whu",
        "name": "武汉大学",
        "aliases": ["Wuhan University", "WHU"],
        "groups": ["985"],
    },
    {"university_id": "hust", "name": "华中科技大学", "aliases": ["HUST"], "groups": ["985"]},
    {
        "university_id": "hnu",
        "name": "湖南大学",
        "aliases": ["Hunan University"],
        "groups": ["985"],
    },
    {
        "university_id": "csu",
        "name": "中南大学",
        "aliases": ["Central South University", "CSU"],
        "groups": ["985"],
    },
    {"university_id": "nudt", "name": "国防科技大学", "aliases": ["NUDT"], "groups": ["985"]},
    {
        "university_id": "sysu",
        "name": "中山大学",
        "aliases": ["Sun Yat-sen University", "SYSU"],
        "groups": ["985"],
    },
    {"university_id": "scut", "name": "华南理工大学", "aliases": ["SCUT"], "groups": ["985"]},
    {
        "university_id": "scu",
        "name": "四川大学",
        "aliases": ["Sichuan University", "SCU"],
        "groups": ["985"],
    },
    {"university_id": "uestc", "name": "电子科技大学", "aliases": ["UESTC"], "groups": ["985"]},
    {
        "university_id": "cqu",
        "name": "重庆大学",
        "aliases": ["Chongqing University", "CQU"],
        "groups": ["985"],
    },
    {
        "university_id": "xjtu",
        "name": "西安交通大学",
        "aliases": ["Xi'an Jiaotong University", "XJTU"],
        "groups": ["985", "c9"],
    },
    {
        "university_id": "nwpu",
        "name": "西北工业大学",
        "aliases": ["NPU", "NWPU"],
        "groups": ["985"],
    },
    {
        "university_id": "lzu",
        "name": "兰州大学",
        "aliases": ["Lanzhou University", "LZU"],
        "groups": ["985"],
    },
    {"university_id": "nwafu", "name": "西北农林科技大学", "aliases": ["NWAFU"], "groups": ["985"]},
    {
        "university_id": "bupt",
        "name": "北京邮电大学",
        "aliases": ["BUPT"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "nuaa",
        "name": "南京航空航天大学",
        "aliases": ["NUAA"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "njust",
        "name": "南京理工大学",
        "aliases": ["NJUST"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "xidian",
        "name": "西安电子科技大学",
        "aliases": ["Xidian University"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "bjut",
        "name": "北京工业大学",
        "aliases": ["BJUT"],
        "groups": ["strong_211"],
    },
    {
        "university_id": "bjtu",
        "name": "北京交通大学",
        "aliases": ["BJTU"],
        "groups": ["strong_211"],
    },
    {
        "university_id": "ustb",
        "name": "北京科技大学",
        "aliases": ["USTB"],
        "groups": ["strong_211"],
    },
    {
        "university_id": "cup",
        "name": "中国石油大学",
        "aliases": ["China University of Petroleum"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "cugb",
        "name": "中国地质大学",
        "aliases": ["China University of Geosciences"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "cumt",
        "name": "中国矿业大学",
        "aliases": ["China University of Mining and Technology"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "cufe",
        "name": "中央财经大学",
        "aliases": ["CUFE"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "suibe",
        "name": "上海对外经贸大学",
        "aliases": ["SUIBE"],
        "groups": ["specialized_strong"],
    },
    {
        "university_id": "uibe",
        "name": "对外经济贸易大学",
        "aliases": ["UIBE"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "shufe",
        "name": "上海财经大学",
        "aliases": ["SHUFE"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "cuel",
        "name": "中南财经政法大学",
        "aliases": ["ZUEL"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "cupl",
        "name": "中国政法大学",
        "aliases": ["CUPL"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "bfsu",
        "name": "北京外国语大学",
        "aliases": ["BFSU"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "shisu",
        "name": "上海外国语大学",
        "aliases": ["SISU"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "cuc",
        "name": "中国传媒大学",
        "aliases": ["CUC"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "dhu",
        "name": "东华大学",
        "aliases": ["Donghua University"],
        "groups": ["strong_211"],
    },
    {
        "university_id": "jiangnan",
        "name": "江南大学",
        "aliases": ["Jiangnan University"],
        "groups": ["strong_211"],
    },
]


PUBLIC_KB_REAL_PUBLIC_SAMPLES: List[Dict[str, Any]] = [
    {
        "sample_id": "pku_2026_recommendation_policy",
        "record_kind": "policy",
        "university_id": "pku",
        "name": "北京大学2026年接收推荐免试研究生办法（校本部）",
        "url": "https://admission.pku.edu.cn/zsxx/sszs/tjms/index.htm",
        "publisher": "北京大学研究生招生网",
        "authority_level": "graduate_school_official",
        "published_at": "2025-09-01",
        "valid_for_year": 2026,
        "summary": "北京大学研究生招生网推荐免试栏目列出校本部2026年接收推荐免试研究生办法，具体政策仍需进入原文或附件核验。",
    },
    {
        "sample_id": "nju_2026_recommendation_policy",
        "record_kind": "policy",
        "university_id": "nju",
        "name": "南京大学2026年接收推荐免试研究生工作办法",
        "url": "https://yzb.nju.edu.cn/07/0a/c47863a788234/page.htm",
        "publisher": "南京大学研究生招生网",
        "authority_level": "graduate_school_official",
        "published_at": "2025-09-10",
        "valid_for_year": 2026,
        "summary": "南京大学研究生招生网发布2026年接收推荐免试研究生工作办法，包含申请材料清单附件和推免工作安排入口。",
    },
    {
        "sample_id": "ustc_2026_recommendation_policy",
        "record_kind": "policy",
        "university_id": "ustc",
        "name": "中国科学技术大学2026年推免生接收办法",
        "url": "https://yz.ustc.edu.cn/article/2793/176?num=-1",
        "publisher": "中国科学技术大学研究生招生在线",
        "authority_level": "graduate_school_official",
        "published_at": "2025-09-01",
        "valid_for_year": 2026,
        "summary": "中国科学技术大学研究生招生在线发布2026年推免生接收办法，列明申请条件、材料和接收程序等信息。",
    },
    {
        "sample_id": "fudan_2026_recommendation_policy",
        "record_kind": "policy",
        "university_id": "fudan",
        "name": "复旦大学2026年招收优秀应届本科毕业生免试攻读研究生章程",
        "url": "https://gsao.fudan.edu.cn/ssyjszszcwzszymlwfslqbf/list1.htm",
        "publisher": "复旦大学研究生招生网",
        "authority_level": "graduate_school_official",
        "published_at": "2025-09-15",
        "valid_for_year": 2026,
        "summary": "复旦大学研究生招生网招生章程目录列出2026年招收优秀应届本科毕业生免试攻读研究生章程。",
    },
    {
        "sample_id": "zju_2026_recommendation_policy",
        "record_kind": "policy",
        "university_id": "zju",
        "name": "浙江大学2026年招收推荐免试研究生办法",
        "url": "https://yz.chsi.com.cn/kyzx/yxzc/202509/20250909/2293407748.html",
        "publisher": "中国研究生招生信息网转载浙江大学",
        "authority_level": "admissions_platform",
        "published_at": "2025-09-09",
        "valid_for_year": 2026,
        "summary": "中国研究生招生信息网转载浙江大学2026年招收推荐免试研究生办法；正式采信时仍应回到浙江大学研究生招生网原始页面核验。",
    },
    {
        "sample_id": "bupt_2026_recommendation_policy",
        "record_kind": "policy",
        "university_id": "bupt",
        "name": "北京邮电大学2026年接收优秀应届本科毕业生免试攻读研究生工作办法",
        "url": "https://zsc.bupt.edu.cn/info/1016/1212.htm",
        "publisher": "北京邮电大学招生网",
        "authority_level": "graduate_school_official",
        "published_at": "2025-09-09",
        "valid_for_year": 2026,
        "summary": "北京邮电大学招生网发布2026年接收优秀应届本科毕业生免试攻读研究生工作办法，包含报考条件、报考流程、考核和录取等信息。",
    },
    {
        "sample_id": "thu_2027_recommendation_registration",
        "record_kind": "policy",
        "university_id": "tsinghua",
        "name": "清华大学2027年接收优秀应届本科毕业生免试攻读研究生报名通知",
        "url": "https://yz.tsinghua.edu.cn/info/1008/3233.htm",
        "publisher": "清华大学研究生招生网",
        "authority_level": "graduate_school_official",
        "valid_for_year": 2027,
        "summary": "清华大学研究生招生网发布2027年推免报名通知；页面说明网上报名、电子材料、申请条件和后续推免服务系统手续，具体院系要求仍需以当年院系通知核验。",
    },
    {
        "sample_id": "thu_2026_recommendation_review",
        "record_kind": "policy",
        "university_id": "tsinghua",
        "name": "清华大学2026年接收推荐免试研究生复试录取办法",
        "url": "https://yz.tsinghua.edu.cn/info/1008/3236.htm",
        "publisher": "清华大学研究生招生网",
        "authority_level": "graduate_school_official",
        "published_at": "2025-09-16",
        "valid_for_year": 2026,
        "summary": "清华大学研究生招生网发布2026级推免复试录取办法；这是历史流程回归样本，具体规则不自动外推到2027级。",
    },
    {
        "sample_id": "thu_2026_recommendation_admission_list",
        "record_kind": "policy",
        "university_id": "tsinghua",
        "name": "清华大学2026年接收推荐免试直硕生、直博生拟录取名单公示",
        "url": "https://yz.tsinghua.edu.cn/info/1024/3251.htm",
        "publisher": "清华大学研究生招生网",
        "authority_level": "graduate_school_official",
        "published_at": "2025-09-22",
        "valid_for_year": 2026,
        "summary": "清华大学研究生招生网发布2026级推免直硕、直博拟录取名单公示；这是历史结果回归样本，不能据此推断后续年度录取规则。",
    },
    {
        "sample_id": "nju_cheng_gong_homepage",
        "record_kind": "advisor",
        "university_id": "nju",
        "name": "龚超 南京大学计算机学院官方个人主页",
        "url": "https://cs.nju.edu.cn/ggm/index.htm",
        "publisher": "南京大学计算机学院",
        "authority_level": "college_official",
        "summary": "南京大学计算机学院托管的教师个人主页，可作为任职和研究方向的候选证据；具体招生资格和年度名额必须另以当年招生通知核验。",
    },
    {
        "sample_id": "nju_tianfan_fu_homepage",
        "record_kind": "advisor",
        "university_id": "nju",
        "name": "傅天凡 南京大学计算机学院官方个人主页",
        "url": "https://cs.nju.edu.cn/futianfan/index.htm",
        "publisher": "南京大学计算机学院",
        "authority_level": "college_official",
        "summary": "南京大学计算机学院托管的教师个人主页，可作为任职和研究方向的候选证据；具体招生资格和年度名额必须另以当年招生通知核验。",
    },
    {
        "sample_id": "scut_2026_recommendation_admission_list",
        "record_kind": "policy",
        "university_id": "scut",
        "name": "华南理工大学2026年接收推荐免试研究生拟录取名单公示",
        "url": "https://yz.scut.edu.cn/2025/0618/c30312a595796/page.htm",
        "publisher": "华南理工大学研究生招生办公室",
        "authority_level": "graduate_school_official",
        "published_at": "2025-06-18",
        "valid_for_year": 2026,
        "summary": "华南理工大学研究生招生办公室公开2026级推免拟录取相关信息；这是历史结果样本，可用于流程回归，不可推断后续年度录取规则。",
    },
    {
        "sample_id": "thu_cs_faculty_directory",
        "record_kind": "advisor",
        "university_id": "tsinghua",
        "name": "清华大学计算机系在职教师目录",
        "url": "https://www.cs.tsinghua.edu.cn/csen/Faculty/Full_time_Faculty.htm",
        "publisher": "清华大学计算机科学与技术系",
        "authority_level": "college_official",
        "summary": "清华大学计算机科学与技术系在职教师目录，可作为导师身份消歧和官方任职信息来源。",
    },
    {
        "sample_id": "tsail_people",
        "record_kind": "advisor",
        "university_id": "tsinghua",
        "name": "TSAIL 课题组 People 页面",
        "url": "https://ml.cs.tsinghua.edu.cn/people.html",
        "publisher": "清华大学 TSAIL",
        "authority_level": "advisor_official",
        "summary": "TSAIL People 页面列出课题组 faculty、postdoc 和研究方向，可用于导师组和实验室生态候选事实。",
    },
    {
        "sample_id": "jianfei_chen_homepage",
        "record_kind": "advisor",
        "university_id": "tsinghua",
        "name": "Jianfei Chen 官方个人主页",
        "url": "https://ml.cs.tsinghua.edu.cn/~jianfei/index.html",
        "publisher": "清华大学 TSAIL",
        "authority_level": "advisor_official",
        "summary": "Jianfei Chen 个人主页说明其任职、研究兴趣和机器学习相关方向，适合进入导师画像候选证据。",
    },
    {
        "sample_id": "jun_zhu_homepage",
        "record_kind": "advisor",
        "university_id": "tsinghua",
        "name": "Jun Zhu 官方个人主页",
        "url": "https://ml.cs.tsinghua.edu.cn/~jun/index.shtml",
        "publisher": "清华大学 TSAIL",
        "authority_level": "advisor_official",
        "summary": "Jun Zhu 个人主页说明其任职、TSAIL 角色和统计机器学习、贝叶斯方法、强化学习等研究方向。",
    },
    {
        "sample_id": "yuxiao_dong_homepage",
        "record_kind": "advisor",
        "university_id": "tsinghua",
        "name": "Yuxiao Dong 官方个人主页",
        "url": "https://keg.cs.tsinghua.edu.cn/yuxiao/",
        "publisher": "清华大学 KEG",
        "authority_level": "advisor_official",
        "summary": "Yuxiao Dong 个人主页说明其任职和大模型、数据挖掘、图机器学习、社交网络等研究方向。",
    },
]

PUBLIC_KB_REAL_PUBLIC_SAMPLES.extend(
    [
        {
            "sample_id": "buaa_2026_recommendation_policy",
            "record_kind": "policy",
            "university_id": "buaa",
            "name": "北京航空航天大学2026年接收推荐免试研究生相关要求",
            "url": "https://yzb.buaa.edu.cn/info/1003/3392.htm",
            "publisher": "北京航空航天大学研究生招生信息网",
            "authority_level": "graduate_school_official",
            "published_at": "2025-09-08",
            "valid_for_year": 2026,
            "summary": "北航研究生招生信息网发布2026年推免申请条件、材料和流程；具体院系安排仍需按当年学院通知核验。",
        },
        {
            "sample_id": "buaa_2026_college_recommendation_notices",
            "record_kind": "policy",
            "university_id": "buaa",
            "name": "北京航空航天大学各学院2026年接收推免研究生通知入口",
            "url": "https://yzb.buaa.edu.cn/info/1036/3399.htm",
            "publisher": "北京航空航天大学研究生招生信息网",
            "authority_level": "graduate_school_official",
            "published_at": "2025-09-08",
            "valid_for_year": 2026,
            "summary": "北航研究生招生网汇总各学院2026年接收推免研究生通知入口，可用于定位院系细则，不能替代具体学院原文。",
        },
        {
            "sample_id": "buaa_2026_recommendation_exam_rules",
            "record_kind": "policy",
            "university_id": "buaa",
            "name": "北京航空航天大学2026年推免复试考场规则",
            "url": "https://yzb.buaa.edu.cn/info/1036/3395.htm",
            "publisher": "北京航空航天大学研究生招生信息网",
            "authority_level": "graduate_school_official",
            "published_at": "2025-09-08",
            "valid_for_year": 2026,
            "summary": "北航研究生招生网公开2026级推免复试考场规则，可作为历史流程和复试要求的回归样本，不自动外推到后续年度。",
        },
        {
            "sample_id": "buaa_cs_faculty_directory",
            "record_kind": "advisor",
            "university_id": "buaa",
            "name": "北京航空航天大学计算机学院全体教师目录",
            "url": "https://scse.buaa.edu.cn/szdw/qtjs/3.htm",
            "publisher": "北京航空航天大学计算机学院",
            "authority_level": "college_official",
            "summary": "北航计算机学院教师目录可用于任职身份和学院归属消歧；导师年度招生资格、名额和联系方式必须另以当年通知核验。",
        },
        {
            "sample_id": "bit_2026_recommendation_policy",
            "record_kind": "policy",
            "university_id": "bit",
            "name": "北京理工大学2026年接收推荐免试研究生办法",
            "url": "https://grd.bit.edu.cn/zsgz/ssyjs/gzzd_ss/1f63040825294e62b5cc2889b5ef49e5.htm",
            "publisher": "北京理工大学研究生院",
            "authority_level": "graduate_school_official",
            "published_at": "2025-09-04",
            "valid_for_year": 2026,
            "summary": "北京理工大学研究生院发布2026年推免接收办法，涉及申请、复试和待录取确认；院系要求应以学院当年通知为准。",
        },
        {
            "sample_id": "bit_2026_master_charter",
            "record_kind": "policy",
            "university_id": "bit",
            "name": "北京理工大学2026年硕士研究生招生章程",
            "url": "https://grd.bit.edu.cn/pub/swzxyjsy/zsgz/ssyjs/gzzd_ss/d48229630a1a43b6baee16c35be5c415.htm",
            "publisher": "北京理工大学研究生院",
            "authority_level": "graduate_school_official",
            "published_at": "2025-10-10",
            "valid_for_year": 2026,
            "summary": "北京理工大学研究生院发布2026年硕士招生章程，其中包含推免相关入口和边界；仅作为该年度政策回归样本。",
        },
        {
            "sample_id": "bit_cs_advisor_directory",
            "record_kind": "advisor",
            "university_id": "bit",
            "name": "北京理工大学计算机学院导师名录",
            "url": "https://cs.bit.edu.cn/szdw/jsml/",
            "publisher": "北京理工大学计算机学院",
            "authority_level": "college_official",
            "summary": "北京理工大学计算机学院导师名录可用于导师身份和学院归属候选证据；不据此推断当年招生名额或接收状态。",
        },
        {
            "sample_id": "bit_cs_doctoral_advisors",
            "record_kind": "advisor",
            "university_id": "bit",
            "name": "北京理工大学计算机学院博士生导师目录",
            "url": "https://cs.bit.edu.cn/szdw/jsml/bssds/index.htm",
            "publisher": "北京理工大学计算机学院",
            "authority_level": "college_official",
            "summary": "北京理工大学计算机学院公开博士生导师目录，适合导师身份消歧和研究方向调研的候选证据。",
        },
        {
            "sample_id": "hit_2026_recommendation_registration",
            "record_kind": "policy",
            "university_id": "hit",
            "name": "哈尔滨工业大学2026年接收推免研究生报名通知",
            "url": "https://yzb.hit.edu.cn/2025/0628/c8817a372823/page.htm",
            "publisher": "哈尔滨工业大学研究生招生办公室",
            "authority_level": "graduate_school_official",
            "published_at": "2025-06-28",
            "valid_for_year": 2026,
            "summary": "哈尔滨工业大学研究生招生办公室发布2026年接收推免研究生报名通知，具体学院材料和复试安排仍需逐项核验。",
        },
        {
            "sample_id": "hit_2026_master_charter",
            "record_kind": "policy",
            "university_id": "hit",
            "name": "哈尔滨工业大学2026年硕士研究生招生章程",
            "url": "https://yzb.hit.edu.cn/2025/0930/c8817a379157/page.psp",
            "publisher": "哈尔滨工业大学研究生招生办公室",
            "authority_level": "graduate_school_official",
            "published_at": "2025-09-30",
            "valid_for_year": 2026,
            "summary": "哈尔滨工业大学2026年硕士招生章程包含推免报名渠道和流程边界，可作为当年公开政策样本。",
        },
        {
            "sample_id": "uestc_2026_recommendation_policy",
            "record_kind": "policy",
            "university_id": "uestc",
            "name": "电子科技大学2026年接收推免研究生通知",
            "url": "https://yz.uestc.edu.cn/info/1082/5574.htm",
            "publisher": "电子科技大学研究生招生网",
            "authority_level": "graduate_school_official",
            "published_at": "2025-09-11",
            "valid_for_year": 2026,
            "summary": "电子科技大学研究生招生网发布2026年接收推免研究生通知，院系具体条件和拟接收数量仍应以学院通知核验。",
        },
        {
            "sample_id": "uestc_2026_master_charter",
            "record_kind": "policy",
            "university_id": "uestc",
            "name": "电子科技大学2026年硕士研究生招生章程",
            "url": "https://yz.uestc.edu.cn/info/1081/5590.htm",
            "publisher": "电子科技大学研究生招生网",
            "authority_level": "graduate_school_official",
            "published_at": "2025-10-09",
            "valid_for_year": 2026,
            "summary": "电子科技大学研究生招生网发布2026年硕士招生章程，含推免制度引用和当年报名边界。",
        },
        {
            "sample_id": "uestc_2026_recommendation_admission_list",
            "record_kind": "policy",
            "university_id": "uestc",
            "name": "电子科技大学各学院2026年推免拟录取名单公示",
            "url": "https://yz.uestc.edu.cn/info/1007/5342.htm",
            "publisher": "电子科技大学研究生招生网",
            "authority_level": "graduate_school_official",
            "published_at": "2025-10-13",
            "valid_for_year": 2026,
            "summary": "电子科技大学公开各学院2026级推免拟录取名单入口；这是历史结果样本，不能用于推断后续年度录取机会。",
        },
        {
            "sample_id": "uestc_2026_admissions_faq",
            "record_kind": "policy",
            "university_id": "uestc",
            "name": "电子科技大学2026年硕士研究生招生热点问题答疑",
            "url": "https://yz.uestc.edu.cn/info/1081/5594.htm",
            "publisher": "电子科技大学研究生招生网",
            "authority_level": "graduate_school_official",
            "published_at": "2025-10-09",
            "valid_for_year": 2026,
            "summary": "电子科技大学研究生招生网的2026年招生答疑可用于识别计划、目录和学院通知之间的证据边界。",
        },
        {
            "sample_id": "hust_2026_recommendation_preregistration",
            "record_kind": "policy",
            "university_id": "hust",
            "name": "华中科技大学2026年接收推免研究生预报名及复试安排",
            "url": "https://gszs.hust.edu.cn/info/1106/4010.htm",
            "publisher": "华中科技大学研究生招生信息网",
            "authority_level": "graduate_school_official",
            "published_at": "2025-09-10",
            "valid_for_year": 2026,
            "summary": "华中科技大学研究生招生信息网发布2026年推免预报名和复试安排，并提示院系细则具有优先核验价值。",
        },
        {
            "sample_id": "hust_2026_recommendation_policy",
            "record_kind": "policy",
            "university_id": "hust",
            "name": "华中科技大学2026年接收推免研究生工作办法",
            "url": "https://gszs.hust.edu.cn/info/1106/4021.htm",
            "publisher": "华中科技大学研究生招生信息网",
            "authority_level": "graduate_school_official",
            "published_at": "2025-09-21",
            "valid_for_year": 2026,
            "summary": "华中科技大学研究生招生信息网发布2026年推免工作办法，可作为政策时效和正式报名流程的公开样本。",
        },
        {
            "sample_id": "hust_cs_faculty_directory",
            "record_kind": "advisor",
            "university_id": "hust",
            "name": "华中科技大学计算机学院教师名录",
            "url": "https://cs.hust.edu.cn/szdw/jsml/ayjslb.htm",
            "publisher": "华中科技大学计算机科学与技术学院",
            "authority_level": "college_official",
            "summary": "华中科技大学计算机学院按研究所公开教师名录，可用于导师身份和研究组织候选证据，不代表当年招生资格。",
        },
        {
            "sample_id": "sysu_2026_recommendation_policy",
            "record_kind": "policy",
            "university_id": "sysu",
            "name": "中山大学2026年接收推荐免试研究生办法",
            "url": "https://graduate.sysu.edu.cn/zsw/article/492",
            "publisher": "中山大学研究生招生网",
            "authority_level": "graduate_school_official",
            "published_at": "2025-09-04",
            "valid_for_year": 2026,
            "summary": "中山大学研究生招生网发布2026年接收推免研究生办法入口，具体附件条款和学院安排须打开原始页面核验。",
        },
        {
            "sample_id": "sysu_2027_recommendation_registration_index",
            "record_kind": "policy",
            "university_id": "sysu",
            "name": "中山大学硕士招生通知列表（含2027年推免报名通知）",
            "url": "https://graduate.sysu.edu.cn/zsw/postgraduate",
            "publisher": "中山大学研究生招生网",
            "authority_level": "graduate_school_official",
            "valid_for_year": 2027,
            "summary": "中山大学研究生招生通知列表包含2027年推免报名通知入口；该列表只用于发现当前通知，具体日期和院系要求需进原文核验。",
        },
        {
            "sample_id": "nwpu_2026_recommendation_preregistration",
            "record_kind": "policy",
            "university_id": "nwpu",
            "name": "西北工业大学2026年接收推荐免试研究生预报名通知",
            "url": "https://yzb.nwpu.edu.cn/info/1174/9898.htm",
            "publisher": "西北工业大学研究生招生信息网",
            "authority_level": "graduate_school_official",
            "published_at": "2025-09-02",
            "valid_for_year": 2026,
            "summary": "西北工业大学研究生招生信息网发布2026年推免预报名通知，最终招生专业和录取结果仍以当年正式系统和学院通知为准。",
        },
        {
            "sample_id": "nwpu_2026_admissions_announcements",
            "record_kind": "policy",
            "university_id": "nwpu",
            "name": "西北工业大学研究生招生公告列表",
            "url": "https://yzb.nwpu.edu.cn/new/sszs/zsgg/16.htm",
            "publisher": "西北工业大学研究生招生信息网",
            "authority_level": "graduate_school_official",
            "valid_for_year": 2026,
            "summary": "西北工业大学研究生招生公告列表可用于定位2026年推免、目录和报名通知，列表本身不能代替具体政策页。",
        },
        {
            "sample_id": "xjtu_2026_recommendation_index",
            "record_kind": "policy",
            "university_id": "xjtu",
            "name": "西安交通大学2026年推免生通知目录",
            "url": "https://yz.xjtu.edu.cn/index/tms.htm",
            "publisher": "西安交通大学研究生招生信息网",
            "authority_level": "graduate_school_official",
            "valid_for_year": 2026,
            "summary": "西安交通大学推免生目录列出2026年推免招生章程、学院实施细则和专业目录入口，具体结论必须进入原始条目核验。",
        },
        {
            "sample_id": "xjtu_2026_recommendation_special_plan",
            "record_kind": "policy",
            "university_id": "xjtu",
            "name": "西安交通大学2026年国优计划推免招生简章",
            "url": "https://yz.xjtu.edu.cn/info/1086/4262.htm",
            "publisher": "西安交通大学研究生招生信息网",
            "authority_level": "graduate_school_official",
            "published_at": "2025-09-09",
            "valid_for_year": 2026,
            "summary": "西安交通大学研究生招生网公开2026年国优计划推免招生简章，是专项政策样本，不可泛化为普通项目规则。",
        },
        {
            "sample_id": "zju_2026_admissions_notice_index",
            "record_kind": "policy",
            "university_id": "zju",
            "name": "浙江大学2026年硕士招生最新通知列表",
            "url": "https://www.grs.zju.edu.cn/yjszs/28498/list.htm",
            "publisher": "浙江大学研究生招生网",
            "authority_level": "graduate_school_official",
            "valid_for_year": 2026,
            "summary": "浙江大学研究生招生最新通知列表包含2026年推免办法和招生简章入口，可用于时效和来源定位。",
        },
        {
            "sample_id": "zju_2026_policy_files_index",
            "record_kind": "policy",
            "university_id": "zju",
            "name": "浙江大学2026年硕士招生政策文件列表",
            "url": "https://www.grs.zju.edu.cn/yjszs/28480/list.htm",
            "publisher": "浙江大学研究生招生网",
            "authority_level": "graduate_school_official",
            "valid_for_year": 2026,
            "summary": "浙江大学研究生招生政策文件列表包含2026年推免办法和免试生目录入口；任何单项名额和截止日期须返回原文确认。",
        },
        {
            "sample_id": "zju_2026_master_charter",
            "record_kind": "policy",
            "university_id": "zju",
            "name": "浙江大学2026年硕士研究生招生简章",
            "url": "https://www.grs.zju.edu.cn/yjszs/2025/1009/c28504a3088958/page.htm",
            "publisher": "浙江大学研究生招生网",
            "authority_level": "graduate_school_official",
            "published_at": "2025-10-09",
            "valid_for_year": 2026,
            "summary": "浙江大学研究生招生网发布2026年硕士招生简章，可用于交叉检查推免服务系统和年度政策边界。",
        },
        {
            "sample_id": "ustc_2026_recommendation_eligibility",
            "record_kind": "policy",
            "university_id": "ustc",
            "name": "中国科学技术大学2026年推免生推荐办法",
            "url": "https://yz.ustc.edu.cn/article/2792/176?num=-1",
            "publisher": "中国科学技术大学研究生招生在线",
            "authority_level": "graduate_school_official",
            "published_at": "2025-09-01",
            "valid_for_year": 2026,
            "summary": "中国科学技术大学研究生招生在线发布2026年推免生推荐办法；推荐与接收规则应按页面类型分别核验。",
        },
        {
            "sample_id": "ustc_2026_recommendation_work_meeting",
            "record_kind": "policy",
            "university_id": "ustc",
            "name": "中国科学技术大学2026年推免工作布置新闻",
            "url": "https://yz.ustc.edu.cn/article/2794/181?num=-1",
            "publisher": "中国科学技术大学研究生招生在线",
            "authority_level": "graduate_school_official",
            "published_at": "2025-09-01",
            "valid_for_year": 2026,
            "summary": "中国科学技术大学研究生招生在线发布2026年推免工作布置新闻，只能作为流程背景来源，不能替代接收办法。",
        },
        {
            "sample_id": "nju_2026_recommendation_notice_index",
            "record_kind": "policy",
            "university_id": "nju",
            "name": "南京大学推免最新公告列表",
            "url": "https://yzb.nju.edu.cn/zxgg/listm1.htm",
            "publisher": "南京大学研究生招生网",
            "authority_level": "graduate_school_official",
            "valid_for_year": 2026,
            "summary": "南京大学推免公告列表包含预报名、工作办法和拟录取公示入口，可用于识别政策阶段和历史结果边界。",
        },
        {
            "sample_id": "bjtu_2026_recommendation_policy",
            "record_kind": "policy",
            "university_id": "bjtu",
            "name": "北京交通大学2026年招收推荐免试攻读硕士（博士）研究生办法",
            "url": "https://gs.bjtu.edu.cn/tzgg/zstzgg/e4c0a4e0405b47d8bb69aeb753191198.htm",
            "publisher": "北京交通大学研究生院",
            "authority_level": "graduate_school_official",
            "published_at": "2025-09-08",
            "valid_for_year": 2026,
            "summary": "北京交通大学研究生院发布2026年推免办法，院系具体考核和最终录取数量仍需以专题网和服务系统确认。",
        },
        {
            "sample_id": "bjtu_2026_recommendation_catalog",
            "record_kind": "policy",
            "university_id": "bjtu",
            "name": "北京交通大学2026年研究生推免招生专业目录",
            "url": "https://gs.bjtu.edu.cn/tzgg/qb/aec6d948aa4545a0bafa0e7adc9f1164.htm",
            "publisher": "北京交通大学研究生院",
            "authority_level": "graduate_school_official",
            "published_at": "2025-09-08",
            "valid_for_year": 2026,
            "summary": "北京交通大学研究生院公开2026年推免招生专业目录；目录中的人数与最终录取人数需要区分。",
        },
        {
            "sample_id": "bjtu_2026_master_charter",
            "record_kind": "policy",
            "university_id": "bjtu",
            "name": "北京交通大学2026年硕士研究生招生简章",
            "url": "https://gs.bjtu.edu.cn/tzgg/qb/d2954595bb1647c7a5b0e3ee04b36fcb.htm",
            "publisher": "北京交通大学研究生院",
            "authority_level": "graduate_school_official",
            "published_at": "2025-10-02",
            "valid_for_year": 2026,
            "summary": "北京交通大学2026年硕士招生简章引用推免办法与专业目录，可用于政策交叉核验。",
        },
        {
            "sample_id": "bjtu_2026_admissions_notice_index",
            "record_kind": "policy",
            "university_id": "bjtu",
            "name": "北京交通大学研究生院招生通知列表",
            "url": "https://gs.bjtu.edu.cn/tzgg/zstzgg/index2.htm",
            "publisher": "北京交通大学研究生院",
            "authority_level": "graduate_school_official",
            "valid_for_year": 2026,
            "summary": "北京交通大学研究生院招生通知列表可用于定位2026年推免办法、专业目录和招生简章；列表本身不支持具体事实结论。",
        },
        {
            "sample_id": "njust_2026_recommendation_policy",
            "record_kind": "policy",
            "university_id": "njust",
            "name": "南京理工大学接收推荐免试生攻读2026年研究生（含直博生）工作办法",
            "url": "https://gs.njust.edu.cn/zsw/68/e1/c4588a354529/page.htm",
            "publisher": "南京理工大学研究生招生网",
            "authority_level": "graduate_school_official",
            "published_at": "2025-09-16",
            "valid_for_year": 2026,
            "summary": "南京理工大学研究生招生网发布2026年推免工作办法，学院细则、报名节点和最终待录取信息仍应以当年通知核验。",
        },
        {
            "sample_id": "njust_2026_recommendation_preregistration",
            "record_kind": "policy",
            "university_id": "njust",
            "name": "南京理工大学2026年推荐免试研究生预报名通知",
            "url": "https://gs.njust.edu.cn/zsw/65/d1/c4587a353745/page.htm",
            "publisher": "南京理工大学研究生招生网",
            "authority_level": "graduate_school_official",
            "published_at": "2025-08-27",
            "valid_for_year": 2026,
            "summary": "南京理工大学预报名通知汇总学院入口，预报名不替代教育部推免服务系统的正式确认流程。",
        },
        {
            "sample_id": "njust_2026_master_charter",
            "record_kind": "policy",
            "university_id": "njust",
            "name": "南京理工大学2026年硕士研究生招生简章及目录",
            "url": "https://gs.njust.edu.cn/zsw/6b/27/c4587a355111/page.htm",
            "publisher": "南京理工大学研究生招生网",
            "authority_level": "graduate_school_official",
            "published_at": "2025-10-29",
            "valid_for_year": 2026,
            "summary": "南京理工大学2026年硕士招生简章及目录包含推免计划与公开招考计划的边界说明。",
        },
        {
            "sample_id": "njust_2026_doctoral_admissions_index",
            "record_kind": "policy",
            "university_id": "njust",
            "name": "南京理工大学博士招生通知列表",
            "url": "https://gs.njust.edu.cn/zsw/bs/list.htm",
            "publisher": "南京理工大学研究生招生网",
            "authority_level": "graduate_school_official",
            "valid_for_year": 2026,
            "summary": "南京理工大学博士招生通知列表包含2026年推免直博相关工作办法入口，可用于区分硕博与直博政策来源。",
        },
        {
            "sample_id": "njust_2026_master_admissions_index",
            "record_kind": "policy",
            "university_id": "njust",
            "name": "南京理工大学硕士招生通知列表",
            "url": "https://gs.njust.edu.cn/zsw/ss/list2.htm",
            "publisher": "南京理工大学研究生招生网",
            "authority_level": "graduate_school_official",
            "valid_for_year": 2026,
            "summary": "南京理工大学硕士招生通知列表可定位2026年推免办法、招生目录和公开招考计划，具体项目条件必须进入原条目确认。",
        },
    ]
)


class PublicKBValidationIssue(BaseModel):
    record_id: str = ""
    source_id: str = ""
    level: Literal["error", "warning"]
    code: str
    message: str


class PublicKBValidationReport(BaseModel):
    valid: bool
    source_count: int = 0
    record_count: int = 0
    chunk_count: int = 0
    issues: List[PublicKBValidationIssue] = Field(default_factory=list)


class PublicKBSeedResult(BaseModel):
    source_count: int = 0
    record_count: int = 0
    chunk_count: int = 0
    university_count: int = 0
    target_groups: List[str] = Field(default_factory=list)


class PublicKBStore:
    """JSONL-backed public KB store under ``workspace/public_kb``."""

    def __init__(self, workspace_or_path: Any):
        root = (
            workspace_or_path.root
            if hasattr(workspace_or_path, "root")
            else Path(workspace_or_path)
        )
        self.root = Path(root) / "public_kb"
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.root / "manifest.json"
        self.sources_path = self.root / "sources.jsonl"
        self.records_path = self.root / "records.jsonl"
        self.chunks_path = self.root / "chunks.jsonl"

    def save_manifest(self, manifest: PublicKBManifest) -> PublicKBManifest:
        self.manifest_path.write_text(_dump(manifest), encoding="utf-8")
        return manifest

    def load_manifest(self) -> PublicKBManifest:
        if not self.manifest_path.exists():
            return PublicKBManifest()
        return PublicKBManifest(**json.loads(self.manifest_path.read_text(encoding="utf-8")))

    def append_source(self, source: PublicKBSource) -> PublicKBSource:
        _append_jsonl(self.sources_path, source)
        return source

    def append_record(self, record: PublicKBRecord) -> PublicKBRecord:
        _append_jsonl(self.records_path, record)
        return record

    def append_chunk(self, chunk: PublicKBChunk) -> PublicKBChunk:
        _append_jsonl(self.chunks_path, chunk)
        return chunk

    def replace_sources(self, sources: Iterable[PublicKBSource]) -> None:
        _write_jsonl(self.sources_path, sources)

    def replace_records(self, records: Iterable[PublicKBRecord]) -> None:
        _write_jsonl(self.records_path, records)

    def replace_chunks(self, chunks: Iterable[PublicKBChunk]) -> None:
        _write_jsonl(self.chunks_path, chunks)

    def sources(self) -> List[PublicKBSource]:
        return _read_jsonl(self.sources_path, PublicKBSource)

    def records(self) -> List[PublicKBRecord]:
        return _read_jsonl(self.records_path, PublicKBRecord)

    def chunks(self) -> List[PublicKBChunk]:
        return _read_jsonl(self.chunks_path, PublicKBChunk)

    def validate(self) -> PublicKBValidationReport:
        sources = self.sources()
        records = self.records()
        chunks = self.chunks()
        source_ids = {item.source_id for item in sources}
        record_ids = {item.record_id for item in records}
        issues: List[PublicKBValidationIssue] = []
        for source in sources:
            if not source.url and source.source_kind == "public_web":
                issues.append(
                    PublicKBValidationIssue(
                        source_id=source.source_id,
                        level="error",
                        code="missing_url",
                        message="公开网页来源必须有 URL",
                    )
                )
            if source.valid_for_year is None and source.source_kind in {"policy", "public_web"}:
                issues.append(
                    PublicKBValidationIssue(
                        source_id=source.source_id,
                        level="warning",
                        code="missing_valid_year",
                        message="政策或网页来源缺少适用年份，只能进入 needs_review",
                    )
                )
        for record in records:
            if not record.source_refs:
                issues.append(
                    PublicKBValidationIssue(
                        record_id=record.record_id,
                        level="error",
                        code="missing_source_ref",
                        message="公开知识事实必须绑定至少一个来源",
                    )
                )
            missing = [ref for ref in record.source_refs if ref not in source_ids]
            if missing:
                issues.append(
                    PublicKBValidationIssue(
                        record_id=record.record_id,
                        level="error",
                        code="unknown_source_ref",
                        message=f"未知 source_id: {', '.join(missing)}",
                    )
                )
            if record.record_kind in {"policy", "deadline"} and record.valid_for_year is None:
                issues.append(
                    PublicKBValidationIssue(
                        record_id=record.record_id,
                        level="warning",
                        code="policy_without_year",
                        message="政策和截止日期缺少年份，不能作为当前建议",
                    )
                )
        for chunk in chunks:
            if chunk.source_id not in source_ids:
                issues.append(
                    PublicKBValidationIssue(
                        record_id=chunk.record_id,
                        source_id=chunk.source_id,
                        level="error",
                        code="unknown_chunk_source",
                        message="chunk 引用了不存在的 source_id",
                    )
                )
            if chunk.record_id not in record_ids:
                issues.append(
                    PublicKBValidationIssue(
                        record_id=chunk.record_id,
                        source_id=chunk.source_id,
                        level="error",
                        code="unknown_chunk_record",
                        message="chunk 引用了不存在的 record_id",
                    )
                )
        return PublicKBValidationReport(
            valid=not any(issue.level == "error" for issue in issues),
            source_count=len(sources),
            record_count=len(records),
            chunk_count=len(chunks),
            issues=issues,
        )

    def search(self, query: str, *, limit: int = 10) -> List[PublicKBRecord]:
        terms = {term.lower() for term in query.split() if term.strip()}
        if not terms:
            return self.records()[:limit]
        scored = []
        for record in self.records():
            haystack = " ".join(
                [
                    record.name,
                    record.summary,
                    *record.aliases,
                    json.dumps(record.structured_facts, ensure_ascii=False),
                ]
            ).lower()
            score = sum(term in haystack for term in terms)
            if score:
                scored.append((score, record.updated_at, record))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [record for _, _, record in scored[:limit]]


def _dump(model: BaseModel) -> str:
    payload = model.model_dump() if hasattr(model, "model_dump") else model.dict()
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _append_jsonl(path: Path, model: BaseModel) -> None:
    payload = model.model_dump() if hasattr(model, "model_dump") else model.dict()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path, model_type: Type[BaseModel]) -> List[Any]:
    if not path.exists():
        return []
    return [
        model_type(**json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def iter_public_records(store: PublicKBStore) -> Iterable[PublicKBRecord]:
    """Yield only public records eligible for remote synchronization."""

    yield from (record for record in store.records() if record.audit_status != "failed")


def default_public_kb_manifest() -> PublicKBManifest:
    groups = sorted({group for item in PUBLIC_KB_TARGET_UNIVERSITIES for group in item["groups"]})
    return PublicKBManifest(
        target_groups=groups,
        universities=PUBLIC_KB_TARGET_UNIVERSITIES,
    )


def seed_target_universities(store: PublicKBStore, *, replace: bool = False) -> PublicKBSeedResult:
    """Seed stable public university entities without inventing policy details."""

    manifest = default_public_kb_manifest()
    source = PublicKBSource(
        source_id="pubsrc_target_university_scope_v1",
        source_kind="manual_summary",
        title="重点高校公开知识库首批范围",
        publisher="Offer Harvester local planning",
        authority_level="manual_summary",
        valid_for_year=None,
        privacy_scope="public",
        audit_status="passed",
        metadata={
            "scope_note": "All 985 universities plus user-confirmed strong 211/specialized schools.",
            "requires_policy_sources": True,
        },
    )
    records: List[PublicKBRecord] = []
    chunks: List[PublicKBChunk] = []
    for item in PUBLIC_KB_TARGET_UNIVERSITIES:
        university_id = str(item["university_id"])
        name = str(item["name"])
        aliases = [str(alias) for alias in item.get("aliases", [])]
        groups = [str(group) for group in item.get("groups", [])]
        record = PublicKBRecord(
            record_id=f"pubrec_university_{university_id}",
            record_kind="university",
            university_id=university_id,
            name=name,
            aliases=aliases,
            summary=f"{name} 属于公开知识库首批目标院校，后续政策、学院和导师事实必须绑定官方来源。",
            structured_facts={
                "groups": groups,
                "policy_detail_status": "needs_official_source",
                "private_student_data_allowed": False,
            },
            source_refs=[source.source_id],
            status="active",
            audit_status="passed",
        )
        chunk = PublicKBChunk(
            chunk_id=f"pubchunk_university_{university_id}_scope",
            record_id=record.record_id,
            source_id=source.source_id,
            title=f"{name} 公开知识库范围记录",
            text=(
                f"{name}（别名：{', '.join(aliases) or '无'}）已纳入保研公开知识库目标范围。"
                "该记录只表示院校实体和范围，不表示任何具体招生政策。"
            ),
            authority_level="manual_summary",
            audit_status="passed",
            embedding_route="external_public",
            metadata={"groups": groups, "university_id": university_id},
        )
        records.append(record)
        chunks.append(chunk)
    if replace:
        store.save_manifest(manifest)
        store.replace_sources([source])
        store.replace_records(records)
        store.replace_chunks(chunks)
    else:
        store.save_manifest(manifest)
        existing_source_ids = {item.source_id for item in store.sources()}
        existing_record_ids = {item.record_id for item in store.records()}
        existing_chunk_ids = {item.chunk_id for item in store.chunks()}
        if source.source_id not in existing_source_ids:
            store.append_source(source)
        for record in records:
            if record.record_id not in existing_record_ids:
                store.append_record(record)
        for chunk in chunks:
            if chunk.chunk_id not in existing_chunk_ids:
                store.append_chunk(chunk)
    return PublicKBSeedResult(
        source_count=1,
        record_count=len(records),
        chunk_count=len(chunks),
        university_count=len(records),
        target_groups=manifest.target_groups,
    )


def seed_real_public_samples(store: PublicKBStore, *, replace: bool = False) -> PublicKBSeedResult:
    """Seed verified public policy and advisor sample metadata.

    The seeded chunks summarize where to verify facts.  They deliberately avoid
    storing full web-page bodies, emails, or private student information.
    """

    sources: List[PublicKBSource] = []
    records: List[PublicKBRecord] = []
    chunks: List[PublicKBChunk] = []
    for item in PUBLIC_KB_REAL_PUBLIC_SAMPLES:
        sample_id = str(item["sample_id"])
        summary = str(item["summary"])
        source_id = f"pubsrc_real_{sample_id}"
        record_id = f"pubrec_real_{sample_id}"
        digest = _content_hash([str(item["name"]), str(item["url"]), summary])
        source = PublicKBSource(
            source_id=source_id,
            source_kind="public_web",
            title=str(item["name"]),
            url=str(item["url"]),
            publisher=str(item["publisher"]),
            authority_level=item.get("authority_level", "unknown"),
            published_at=str(item.get("published_at", "")),
            valid_for_year=item.get("valid_for_year"),
            content_hash=digest,
            robots_status="not_checked_manual_seed",
            tos_status="not_checked_manual_seed",
            privacy_scope="public",
            audit_status="passed",
            metadata={
                "manual_seed": True,
                "sample_id": sample_id,
                "body_stored": False,
                "requires_live_connector_check": True,
            },
        )
        record = PublicKBRecord(
            record_id=record_id,
            record_kind=item["record_kind"],
            university_id=str(item.get("university_id", "")),
            name=str(item["name"]),
            summary=summary,
            structured_facts={
                "source_url": str(item["url"]),
                "publisher": str(item["publisher"]),
                "body_stored": False,
                "fact_detail_status": "summary_only_needs_original_page_check",
            },
            source_refs=[source_id],
            valid_for_year=item.get("valid_for_year"),
            status="active",
            audit_status="passed",
        )
        chunk = PublicKBChunk(
            chunk_id=f"pubchunk_real_{sample_id}_summary",
            record_id=record_id,
            source_id=source_id,
            title=str(item["name"]),
            text=summary,
            url=str(item["url"]),
            content_hash=digest,
            valid_for_year=item.get("valid_for_year"),
            authority_level=item.get("authority_level", "unknown"),
            audit_status="passed",
            embedding_route="external_public",
            metadata={
                "sample_id": sample_id,
                "record_kind": str(item["record_kind"]),
                "summary_only": True,
            },
        )
        sources.append(source)
        records.append(record)
        chunks.append(chunk)

    if replace:
        store.replace_sources(sources)
        store.replace_records(records)
        store.replace_chunks(chunks)
    else:
        store.replace_sources(
            [item for item in store.sources() if not item.source_id.startswith("pubsrc_real_")]
            + sources
        )
        store.replace_records(
            [item for item in store.records() if not item.record_id.startswith("pubrec_real_")]
            + records
        )
        store.replace_chunks(
            [item for item in store.chunks() if not item.chunk_id.startswith("pubchunk_real_")]
            + chunks
        )
    return PublicKBSeedResult(
        source_count=len(sources),
        record_count=len(records),
        chunk_count=len(chunks),
        university_count=0,
        target_groups=["verified_public_policy_samples", "verified_public_advisor_samples"],
    )


def _content_hash(parts: Iterable[str]) -> str:
    payload = "\n".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_jsonl(path: Path, models: Iterable[BaseModel]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for model in models:
            payload = model.model_dump() if hasattr(model, "model_dump") else model.dict()
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
